# Security Incident Report: Legacy Context Accessors Leak (CVE-Internal-2026-01)

**Date:** 2026-01-26
**Component:** Rust Core ([src/structures.rs](../../../src/structures.rs), [src/guards.rs](../../../src/guards.rs))
**Severity:** HIGH (Integrity Violation)
**Status:** ✅ RESOLVED

---

## 1. Mô Tả Sự Cố (Incident Description)
Trong quá trình Audit mã nguồn Theus v3.0.2, chúng tôi phát hiện ra một lỗ hổng nghiêm trọng liên quan đến các phương thức truy cập context cũ (Legacy Accessors): `ctx.domain_ctx` và `ctx.global_ctx`.

*   **Vấn đề:** Các phương thức này trả về tham chiếu trực tiếp (Raw Reference) đến các đối tượng dữ liệu bên trong [State](../../../theus/structures.py) (hoặc được wrap không đúng cách), bỏ qua cơ chế bảo vệ [SupervisorProxy](../../../src/proxy.rs) chuẩn.
*   **Hậu quả:** Developer có thể vô tình hoặc cố ý thay đổi trạng thái hệ thống (State Mutation) mà không thông qua Transaction Manager.
    *   Vi phạm nguyên tắc "Immutable Global State".
    *   Tạo ra "Shadow Zone" (dữ liệu bị thay đổi cục bộ nhưng không được commit), gây mất đồng bộ state.
    *   Bypass hệ thống Audit log.

## 2. Phân Tích Nguyên Nhân (Root Cause Analysis)

### 2.1. Legacy Design (Di sản mã nguồn)
Trong Theus v2, [domain_ctx](../../../examples/async_outbox/context.py) và [global_ctx](../../../src/structures.rs) được tạo ra để map trực tiếp vào dictionary. Khi chuyển sang v3 (Rust Core), các getters này được port sang nhưng trỏ thẳng vào `state.data["domain"]`.
Mặc dù [State](../../../theus/structures.py) lưu trữ `Arc<PyObject>`, việc trả về object này cho Python cho phép Python code thay đổi nội dung bên trong (nếu là Dict/List) mà Rust không hề hay biết (Reference Leak).

### 2.2. Logic Gap trong [ContextGuard](../../../src/guards.rs)
Khi [ContextGuard](../../../src/guards.rs) phát hiện một đối tượng đã là [SupervisorProxy](../../../src/proxy.rs) (ví dụ: khi truy cập `ctx.domain` chuẩn), nó thực hiện logic "Upgrade" (từ Read-Only server-side sang Write-Client-side).
Tuy nhiên, logic cũ **QUÊN KHÔNG GỌI [get_shadow()](../../../src/engine.rs)**.
*   **Hành vi sai:** Nó unwrap proxy cũ -> lấy reference gốc -> wrap vào proxy mới.
*   **Hệ quả:** Proxy mới trỏ vào reference gốc. Khi ghi (write), nó ghi thẳng vào Global State gốc!

## 3. Giải Pháp Khắc Phục (Resolution)

Chúng tôi đã thực hiện một bản vá gồm 2 lớp (Defense-in-Depth):

### 3.1. Layer 1: Secure Alias Restoration ([src/structures.rs](../../../src/structures.rs))
Thay vì xóa bỏ [global_ctx](../../../src/structures.rs) (gây lỗi cú pháp cho code cũ), chúng tôi chuyển đổi chúng thành **Safe Aliases**.
```rust
// Trước (Nguy hiểm):
fn global_ctx(...) { return self.data["global"]; }

// Sau (An toàn):
fn global_ctx(...) { return self.state.getattr("global"); } // Gọi qua SupervisorProxy chuẩn
```
Điều này đảm bảo mọi truy cập đều đi qua cổng chính thức.

### 3.2. Layer 2: Transaction Shadow Enforcement ([src/guards.rs](../../../src/guards.rs))
Bổ sung logic bắt buộc tạo bản sao (Shadow Copy) khi unwrap một Proxy.

```rust
// CRITICAL FIX in ContextGuard::apply_guard
if let Ok(target) = val_bound.getattr("supervisor_target") {
    let inner = target.unbind();
    // BẮT BUỘC: Tạo bản sao Transaction trước khi cho phép ghi
    let shadow = tx.get_shadow(inner, path)?; 
    return SupervisorProxy::new(shadow, ...);
}
```

## 4. Xác Minh (Verification)

Sử dụng script kiểm tra chuyên dụng: [tests/manual/verify_domain_ctx_leak.py](../../../tests/manual/verify_domain_ctx_leak.py).

| Test Case | Trước khi Fix | Sau khi Fix | Đánh giá |
| :--- | :--- | :--- | :--- |
| **API Compliance** | `ctx.global_ctx` OK | `ctx.global_ctx` OK | ✅ Tương thích ngược |
| **Mutation Attempt** | Allowed (Ghi thẳng vào State) | Allowed (Ghi vào Shadow) | ✅ Hành vi đúng |
| **Global State Check** | **666 (Corrupted)** | **100 (Immutable)** | ✅ **SECURE** |

## 5. Kết Luận
Hệ thống hiện tại đã an toàn tuyệt đối trước lỗi Reference Leak này. Developer có thể sử dụng `ctx.domain` hoặc `ctx.domain_ctx` thay thế cho nhau mà không lo ngại về tính toàn vẹn dữ liệu.
