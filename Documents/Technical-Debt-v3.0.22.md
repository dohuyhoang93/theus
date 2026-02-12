# 📉 Technical Debt Report (v3.0.22)

**Report Date:** 11/02/2026  
**Status:** Post-Optimization & Stabilization Phase.

---

## 1. Accepted Risks (Trade-offs)

Những vấn đề này ĐÃ được xác định, Audit kỹ lưỡng, và quyết định **chấp nhận** trong ngắn hạn để đảm bảo tính ổn định hoặc vì lý do kiến trúc (systems_analysis_shadow_copy.md).

### Risk 1: GC Pressure (Deepcopy)
*   **Mô tả:** Mọi access vào Data Zone đều trigger `deepcopy` toàn bộ object (O(N)).
*   **Impact:** Tốn ~9MB memory cho dict 10K keys.
*   **Mitigation:** Đã có Heavy Zone (Zero-Copy) cho dữ liệu lớn. Logic tách biệt rõ ràng.
*   **Future Plan:** Implement "Lazy Shadow" (Copy-on-Write granular) cho v3.4+.

### Risk 5: O(N) Delta Logging
*   **Mô tả:** Khi gọi `.append()` trên List Proxy, toàn bộ List mới được clone và log vào delta (thay vì chỉ log phần tử mới).
*   **Impact:** Delta log phình to theo kích thước List.
*   **Justification:** Đảm bảo correctness tuyệt đối cho Phase hiện tại. Performance chấp nhận được.
*   **Future Plan:** Implement "Operational Delta" (chỉ log operation `path.append(val)`). Cần thay đổi kiến trúc `infer_shadow_deltas`.

---

## 2. Pre-existing Failures (Cần Fix Sớm)

Những test cases đang fail trong regression suite nhưng không chặn release v3.0.22 (Non-blocking).

### 2.1. `test_schema_gatekeeper`
*   **Lỗi:** `AttributeError: Wrapped object has no to_dict`.
*   **Nguyên nhân:** Proxy wrapper che khuất method của object gốc. Cần implement `__getattr__` delegation thông minh hơn hoặc fix test case để truy cập `inner`.
*   **Priority:** Medium.

### 2.2. `test_zero_copy_proof` (Flaky Performance)
*   **Lỗi:** Heavy Zone access time ~37ms (vượt ngưỡng lý thuyết 2ms).
*   **Nguyên nhân:** Overhead initialization của `SupervisorProxy` và PyO3 conversion cho object lớn. Dù đã tối ưu 30x (giảm từ 1000ms), nó vẫn chưa đạt "Zero-cost".
*   **Priority:** Low (Acceptable for now).

---

## 3. Structural Debt (Nợ Cấu Trúc)

Cần refactor để clean code và tránh lỗi tiềm ẩn.

### 3.1. Project Structure Conflict
*   **Vấn đề:** Folder `theus_core` (Rust source) nằm ở root, trùng tên với module binary `theus_core.pyd` được install.
*   **Hậu quả:** Không thể chạy test từ root project nếu install dạng non-editable (Python import nhầm folder rỗng thay vì binary).
*   **Giải pháp:** Move Rust source vào thư mục `src/` hoặc `rust/`. Cần update `pyproject.toml` và `maturin` config.

### 3.2. Logic Duplication (`deep_merge_cow`)
*   **Vấn đề:** Logic merge object tồn tại ở 2 nơi: `structures.rs` và `utils.rs`.
*   **Rủi ro:** Logic drift khi sửa một bên quên bên kia.
*   **Giải pháp:** Unify về một source duy nhất.

---

## 4. Documentation Debt

### 4.1. Rust Trace Logging Strategy
*   **Trạng thái:** Đã remove hết `println!` debug để fix performance.
*   **Nợ:** Cần thêm logging chuẩn (với feature flag `log` crate hoặc `tracing` crate) để debug production mà không ảnh hưởng performance mặc định. Hiện tại debug bằng cách insert code thủ công.

---
**Tác giả:** Antigravity AI @ 3.0.22 Release Candidate.
