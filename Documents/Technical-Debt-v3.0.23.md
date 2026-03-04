# 📉 Technical Debt Report (v3.0.23)

**Report Date:** 11/02/2026  
**Status:** Post-Critical Fix (Hotfix Logic).

---

## 0. Resolved Issues (Mới Fix) 🌟

Những vấn đề nghiêm trọng phát sinh đã được xử lý ngay lập tức trong phiên debug vừa qua:

### 0.1. Split-Brain Proxy (Silent Loss) [CRITICAL]
*   **Lỗi:** Mất dữ liệu khi thực hiện in-place mutation (vd: `append`) trên nested list/dict (Items `append` bị lost).
*   **Nguyên nhân:** Proxy con tự động tạo `get_shadow` mới, dẫn đến việc có 2 bản copy tách biệt (Split-Brain) thay vì dùng chung bản copy của cha.
*   **Giải Pháp:** Cập nhật `proxy.rs` để Proxy con kế thừa trạng thái `is_shadow` từ cha (`is_child_shadow` flag), đảm bảo mọi mutation đều hướng về cùng một memory address.
*   **Verification:** Verified PASS với `repro_silent_loss.py`.

### 0.2. Code Duplication
*   **Vấn đề:** Duplicate import `copy_mod` trong `engine.rs` (tạo warning khi compile).
*   **Giải Pháp:** Đã xóa code thừa (Refactor clean up).

---

## 1. Accepted Risks (Trade-offs) - Vẫn Còn Nguyên

Những vấn đề này ĐÃ được xác định và quyết định **chấp nhận** trong ngắn hạn:

### Risk 1: GC Pressure (Deepcopy)
*   **Mô tả:** Mọi access vào Data Zone đều trigger `deepcopy` toàn bộ object (O(N)).
*   **Impact:** Tốn ~9MB memory cho dict 10K keys.
*   **Plan:** Lazy Shadow (v3.4+).

### Risk 5: O(N) Delta Logging
*   **Mô tả:** Khi gọi `.append()` trên List Proxy, toàn bộ List mới được clone và log vào delta.
*   **Plan:** Operational Delta.

---

## 2. Pre-existing Failures (Known Bugs)

### 2.1. `test_schema_gatekeeper`
*   **Lỗi:** `AttributeError: Wrapped object has no to_dict`. Proxy wrapper chưa delegate attribute này.
*   **Priority:** Medium.

### 2.2. `test_zero_copy_proof` (Flaky Performance)
*   **Lỗi:** Access Heavy Zone chậm hơn lý thuyết (37ms vs 2ms). Zero-copy chưa đạt chuẩn tuyệt đối do overhead init.

### 2.3. `test_silent_loss_comprehensive` (New Known Issue)
*   **Lỗi:** Case `Replacement` (gán đè list: `items = new_list`) sau đó `Append` vẫn thất bại trong bài test tổng hợp.
*   **Status:** Pending Investigation. (Low Priority compared to In-place fix which is now done).

---

## 3. Structural Debt (Nợ Cấu Trúc)

### 3.1. Project Structure Conflict
*   **Vấn đề:** Folder `theus_core` (Rust source) nằm ở root, trùng tên với module binary `theus_core` được install.
*   **Hậu quả:** Không thể chạy test từ root project nếu install dạng non-editable.
*   **Workaround:** Đã dùng script rename folder tạm thời khi chạy test.
*   **Fix cần:** Move Rust source vào thư mục `src/` hoặc `rust/`.

### 3.2. Logic Duplication (`deep_merge_cow`)
*   **Vấn đề:** Logic merge object tồn tại ở 2 nơi: `structures.rs` và `utils.rs`.

---

## 4. Documentation Debt

### 4.1. Rust Trace Logging Strategy
*   **Status:** Đã clean debug prints. Cần thêm thư viện logging chuẩn (tracing crate).

---
**Tác giả:** Antigravity AI @ v3.0.23 (Critical Fix Released)
