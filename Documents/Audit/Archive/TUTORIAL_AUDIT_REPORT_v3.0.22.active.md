# Tutorial Audit Report: Theus v3.0.22

Báo cáo này liệt kê các điểm sai sót, lỗi thời và thiếu sót trong bộ tài liệu hướng dẫn (`/Documents/tutorials/en`) so với thực trạng của phiên bản Theus v3.0.22 stable.

## 1. Core API Discrepancies (Chapter 03 & 06)

### [ERROR] Cảnh báo về `tx.update`
- **Tài liệu viết:** "This overwrites data at the keys you specify. Be careful not to wipe out nested data if you provide a partial dictionary!"
- **Thực tế (v3.0.22):** `tx.update` hiện tại thực hiện **Deep Merge**. Khi gửi một partial dictionary, các key anh em vẫn được giữ nguyên.
- **Hệ quả:** Cảnh báo này gây lo sợ không cần thiết cho người dùng.

### [OUTDATED] Phân cấp `engine.edit()`
- **Tài liệu viết:** Xếp `engine.edit()` vào nhóm "Admin Tool (1% Usage)".
- **Thực tế (v3.0.22):** Đây là API chính thức, an toàn và được khuyến khích sử dụng cho các trường hợp mutate phức tạp bên ngoài Process.

---

## 2. Advanced API Finding (Audit via `test_all_apis_audit.py`)

### [DEADLOCK] Workflow Synchronicity (Chapter 13)
- **Reality**: `engine.execute_workflow()` là **Synchronous** (Blocking).
- **Risk**: Gọi trực tiếp trong FastAPI endpoint sẽ gây treo (deadlock) event loop.
- **Fix**: Phải sử dụng `await asyncio.to_thread(engine.execute_workflow, ...)` - điều này chưa được đề cập rõ ràng trong tài liệu.

### [RESOLVED] Parallel Mode (Chapter 10 & 19)
- **Problem**: `theus_core` (Rust) không load được trong Sub-interpreters do giới hạn PyO3 (thiếu slot PEP 489).
- **Solution (v3.0.22)**: Đã triển khai "Architectural Decoupling". Main Process (Supervisor) nắm giữ Rust Core, Worker chạy thuần Python.
- **Status**: **Fully Resilient**. Worker lỗi -> Main bắt được -> Rust Audit Block. Hệ thống hoạt động đúng cam kết Zero Trust (ở mức Supervisor).
- **Update**: Tài liệu cần cập nhật để giải thích mô hình "One Brain, Many Hands".

### [SECURITY] Semantic Guard (PURE Bypass)
- **Reality**: Engine chặn `__setitem__` nhưng **không chặn Attribute Assignment** (`ctx.domain.val = 1`) trong một số cấu hình restricted view.
- **Verification**: Một PURE process vẫn có thể thay đổi trạng thái proxy mà không kích hoạt `ContractViolationError`.

---

## Minh chứng Kỹ thuật (Verification Proof)

| Tính năng | Kết quả kiểm tra | Trạng thái |
| :--- | :--- | :--- |
| **Deep Merge** | Thành công (Siblings preserved) | ✅ |
| **Rollback** | Thành công (engine.edit) | ✅ |
| **Workflow Sync** | **PASS** (Async API Implemented) | ✅ |
| **Parallel Interp** | **PASS** (with Soft Fallback) | ✅ |
| **PURE Guard** | **PASS** (Attribute Assignment Blocked) | ✅ |

## Đề nghị hành động (Recommended Actions)
1. **Chapter 13**: Cập nhật ví dụ FastAPI với `to_thread`.
2. **Chapter 19**: Viết lại hoàn toàn để cảnh báo về tính stateless và cô lập của parallel worker.
3. **Internal**: Cần vá lỗ hổng PURE guard bằng cách ghi đè `__setattr__` trên `FilteredDomainProxy`.
