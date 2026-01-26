# Phân tích Phản biện: Lỗi Hệ thống Phân quyền Theus v3.1 (Post-Mortem)

**Trạng thái:** ĐÃ SỬA (FIXED)
**Ngày:** 23/01/2026
**Phạm vi:** `theus_core::guards` / `theus.engine`

## GIAI ĐOẠN 1: 8 QUY TẮC PHÂN TÍCH CỐT LÕI

### 1. Xác định Vấn đề (Problem Statement)
Hàm `app_logic_process` của người dùng gặp lỗi `PermissionError: PURE process cannot write to 'domain.counter'`. Lỗi này chặn đứng giá trị cốt lõi của Theus v3.1 (Kiến trúc Supervisor): cho phép thay đổi trạng thái (mutation) được quản lý trong môi trường an toàn.

### 2. Phạm vi Điều tra (Inquiry Scope)
- **Nguyên nhân gốc:** Tại sao quyền Read-Only bị cưỡng chế nghiêm ngặt dù `ContextGuard` đã được bật cờ "Admin Mode"?
- **Cơ chế:** Cách `ContextGuard` tương tác với `SupervisorProxy` qua ranh giới Rust/Python (FFI).
- **Khoảng hở Kiến trúc:** Sự đứt gãy giữa kỳ vọng "Implicit Transaction" (Giao dịch ngầm) của Python và yêu cầu "Explicit Transaction" (Giao dịch tường minh) của Rust.

### 3. Tính Toàn vẹn Dữ liệu (Data Integrity)
- **Bằng chứng:** Log debug xác nhận `DEBUG: No Transaction for guard path 'domain', returning raw value`.
- **Trạng thái Đối tượng:** Đối tượng trả về là `SupervisorProxy(read_only=True)`.
- **Kiểm chứng:** Đã xác minh bằng `comprehensive_api_test_v3_1.py`, test case thất bại liên tục cho đến khi Transaction được tiêm vào.

### 4. Sự Minh bạch về Khái niệm (Conceptual Clarity)
- **Khái niệm:** *Context Elevation* (Nâng cấp Ngữ cảnh). Các đối tượng Read-Only (từ `State`) phải được "Nâng cấp" thành các wrapper Mutable (được bảo trợ bởi một Transaction) khi đi vào một Process.
- **Thất bại:** Logic Nâng cấp phụ thuộc vào sự hiện diện của một đối tượng `Transaction`. Việc thiếu đối tượng này khiến hệ thống âm thầm quay về (fallback) tham chiếu Read-Only gốc.

### 5. Tính Nhất quán Logic (Logical Consistency)
- **Lỗ hổng:** Cài đặt cũ của `engine.py` giả định rằng `execute_process_async` sẽ tự xử lý toàn bộ vòng đời transaction bên trong Rust.
- **Thực tế:** `ContextGuard` (API phía Python) cần một đối tượng `Transaction` phía Python để ghi log các thay đổi (`log_internal`). Mã nguồn không nhất quán: nó tạo Guard nhưng lại bỏ đói dependency của nó (`tx=None`).

### 6. Hệ quả & Tác động (Implications & Consequences)
- **Nếu bỏ qua:** Người dùng sẽ buộc phải dùng khối lệnh `engine.transaction()` thủ công trong mọi hàm, làm mất đi lợi ích trải nghiệm người dùng của decorator `@process`.
- **Khi đã sửa:** Khôi phục độ "Mượt" (Magic) của framework trong khi vẫn duy trì tính bảo mật nghiêm ngặt của Rust Supervisor.

### 7. Các Giả định (Assumptions & Presuppositions)
- **Giả định sai:** "Rust Core lo hết mọi thứ."
- **Điều chỉnh:** Rust Core lo phần *lưu trữ và xác thực*, nhưng Python Layer phải điều phối *chất keo kết dính vòng đời* (tạo đối tượng Tx, commit kết quả) vì Giao diện Người dùng nằm ở Python.

### 8. Góc nhìn & Chiều rộng (Perspective & Breadth)
- **Góc nhìn Vi mô:** Một lỗi nhỏ về tham số trong `engine.py`.
- **Góc nhìn Vĩ mô:** Một sự xác thực cho mô hình "Supervisor". Hệ thống đã thành công trong việc chặn các ghi chép không được ủy quyền (lỗi ở đây là các ghi chép *được ủy quyền* lại bị coi là không được phép). Cơ chế bảo mật đã hoạt động *quá tốt*.

---

## GIAI ĐOẠN 2: PHÂN TÍCH ĐỘ PHỨC TẠP & CÁC TRƯỜNG HỢP

### Trường hợp Tiêu chuẩn (Model Case)
- **Kịch bản:** Người dùng tăng biến dem: `ctx.domain.counter += 1`.
- **Luồng:**
    1. `ContextGuard` nhận được `tx`.
    2. Truy cập `domain` kích hoạt `apply_guard`.
    3. `apply_guard` thấy `tx`, mở gói Proxy Read-Only (`supervisor_target`), và gói lại vào một Mutable `SupervisorProxy` liên kết với `tx`.
    4. Code thực thi.
    5. Engine commit `tx.pending_data`.
- **Kết quả:** Thành công.

### Các Trường hợp Liên quan (Related Cases - Nested Structures)
- **Kịch bản:** Người dùng sửa `ctx.domain.nested['key'] = val`.
- **Phân tích:** `ContextGuard` phải lan truyền tham chiếu `tx` xuống các đối tượng con. Thuộc tính `supervisor_target` đảm bảo ngay cả các proxy con Read-Only cũng có thể được nâng cấp.

### Các Trường hợp Biên (Edge Cases)
- **Ép kiểu `list` sai:** Người dùng thử `return list(ctx.domain.counter)`.
    - **Vấn đề:** `counter` là `int`. Lỗi này không thuộc về Framework mà là lỗi logic người dùng.
    - **Xử lý:** Framework trả về `int` chính xác. Python raise `TypeError` chuẩn.
- **Thiếu `try/except` trong Engine:**
    - **Rủi ro:** Nếu thực thi rớt, Audit Log có thể bị bỏ qua hoặc Commit diễn ra một nửa.
    - **Giảm thiểu:** Khối `try...execute...commit...except` nghiêm ngặt đảm bảo tính Nguyên tử (Atomicity).

### Các Trường hợp Xung đột (Conflict Cases)
- **Kịch bản:** Hai process cùng sửa một trường dữ liệu đồng thời.
- **Hành vi:**
    1. Cả hai chạy Optimistic.
    2. Cả hai commit vào `compare_and_swap`.
    3. **Rust Core (Smart CAS)** phát hiện xung đột cấp trường (Field-Level).
    4. Một bên lỗi `ContextError`.
    5. **Engine Logic:** Bắt lỗi -> Retry loop -> Tạo lại `tx` mới -> Chạy lại.
    6. **Hệ thống tự phục hồi.**

---

## GIAI ĐOẠN 3: GIẢI PHÁP & GIẢM THIỂU RỦI RO

### 1. Giải pháp Cốt lõi (Đã triển khai)
- **Vòng đời Tường minh:** Sửa `engine.py` để khởi tạo `theus_core.Transaction` một cách tường minh.
- **Tiêm phụ thuộc (Injection):** Truyền transaction này vào `ContextGuard`.
- **Commit:** Thêm bước `self._core.compare_and_swap(..., data=tx.pending_data)` sau khi thực thi.

### 2. Khả năng Thích ứng (Adaptability)
- **Transaction Getters:** Expose các thuộc tính `pending_data`, `pending_heavy`, `pending_signal` từ Rust ra Python. Cho phép Python kiểm tra hoặc can thiệp vào transaction trước khi commit nếu cần.

### 3. Khả năng Phục hồi (Resilience)
- **IO Flushing:** Thêm `std::io::Write` và `flush()` vào log debug Rust để đảm bảo khả năng điều tra (forensic) trong tương lai nếu crash.
- **An toàn kiểu (Type Safety):** `ContextGuard` giờ đây kiểm tra `supervisor_target` một cách tường minh, ngăn chặn việc "Gói mù" (Blind Wrapping).

### 4. Phương án Dự phòng (Fallback)
- **Strict Mode:** Nếu thiếu `tx` (ví dụ trong view Read-Only), `ContextGuard` xuống cấp nhẹ nhàng về chế độ Read-Only (trả về raw assertions). Ngăn chặn "Hành vi không xác định" (Undefined Behavior) – nó hoặc hoạt động ghi được, hoặc chỉ đọc, không bao giờ bị crash "giữa chừng".

---

**Kết luận:** Kiến trúc vững chắc. Khoảng hở trong `engine.py` đã được lấp đầy. Hệ thống hiện tuân thủ hoàn toàn mẫu thiết kế Supervisor.
