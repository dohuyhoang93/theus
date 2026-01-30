# 📄 Phân tích Tư duy Phản biện: Quản lý Side Effect và Error

> **Phương pháp luận:** Paul-Elder Critical Thinking.
> **Triết lý:** Phi Nhị Nguyên (Controlled Chaos).

---

## 1. Mổ xẻ Vấn đề (Deconstruction)

### 1.1. Mục đích (Purpose)
Chúng ta muốn xây dựng một hệ thống **Minh bạch (Transparent)** nhưng không **Cứng nhắc (Rigid)**.
*   Nếu chặn Side Effect quá chặt -> Dev không làm được gì (như Haskell).
*   Nếu thả lỏng Side Effect -> Hệ thống thành "Spaghetti Code".

### 1.2. Khái niệm (Concepts)
*   **Pure Logic:** Code chỉ tính toán, không I/O. (Dễ quản lý).
*   **Side Effect:** Code tương tác với thế giới thực (Ghi file, Gọi API, In màn hình). (Khó quản lý).
*   **Error:** Sự cố bất ngờ. (Cần phục hồi).

---

## 2. Phân tích Chiến lược: Side Effect Management

### 2.1. Hiện trạng (AS-IS)
Hiện tại `pop-sdk` chỉ coi Side Effect là **Metadata** (Tài liệu). Engine không có cơ chế chặn thực thi.

### 2.2. Phổ giải pháp Phi Nhị Nguyên (The Solution Spectrum)

| Cấp độ | Giải pháp | Ưu điểm | Nhược điểm |
| :--- | :--- | :--- | :--- |
| **Level 0 (Free)** | **Documentation First:** Chỉ yêu cầu khai báo `@process(side_effects=['log'])`. Không check gì cả. | Nhanh, dễ dev. | Dễ sai con người. |
| **Level 1 (DI)** | **Dependency Injection:** Mọi I/O phải đi qua `ctx.adapter`. Cấm dùng `open()`, `print()` trực tiếp. | Testable (Mock được). | Hơi rườm rà. |
| **Level 2 (Sandbox)** | **OS Isolation:** Dùng WASM/Docker để chặn Syscall. Process không thể mở file nếu không được cấp quyền. | An toàn tuyệt đối. | Chậm, khó setup. |

### 2.3. Đề xuất Chiến lược POP
Chọn con đường trung đạo: **Adapter Pattern (Level 1+)**.
1.  **Rule:** Cấm `import os`, `import requests` trong Process.
2.  **Facilitator:** Engine cung cấp `system_ctx.resources`.
    *   Thay vì `open('file.txt')`, Dev gọi `Resources.files.write('file.txt')`.
    *   Engine có thể chèn logic Audit/Rate Limit vào cái hàm `write` này.
    *   Đây là cách để "trói" Side effect vào Managed Context.

---

## 3. Phân tích Chiến lược: Error Management

### 3.1. Hiện trạng (AS-IS)
Engine đang bắt lỗi (Try-Catch). Nếu lỗi chưa khai báo trong Contract -> Raise `UndeclaredError`.
**Lợi:** Ép dev suy nghĩ về mọi lỗi có thể xảy ra.
**Hại:** Đôi khi quá cứng nhắc với các lỗi Run-time (như OutOfMemory).

### 3.2. Phổ giải pháp Phi Nhị Nguyên

| Chiến lược | Tư duy | Hành động |
| :--- | :--- | :--- |
| **Let it Crash** (Erlang) | Lỗi là không tránh khỏi. Đừng sửa. Hãy Reset. | Process chết -> Restart Process với data cũ. |
| **Defensive** (Java) | Cố gắng bắt mọi lỗi. | Try-Catch chằng chịt. Code xấu. |
| **Compensating** (SAGA) | Lỗi là một phần của quy trình. | Process A lỗi -> Gọi Process A_Revert để dọn dẹp. |

### 3.3. Đề xuất Chiến lược POP
Sử dụng **Smart Recovery Strategy**:
1.  **Categorization:** Phân loại lỗi ngay trong Contract.
    *   `TransientError` (Lỗi mạng): -> **Retry** (Tự động thử lại 3 lần).
    *   `LogicError` (Bug code): -> **FailFast** (Dừng ngay để sửa).
    *   `ResourceError` (Hết disk): -> **Compensate** (Chạy quy trình dọn dẹp).
2.  **Implementation:**
    ```python
    @process(
        errors={
            "NetworkError": Recovery.Retry(3),
            "ValueError": Recovery.Fail
        }
    )
    ```

---

## 4. Kết luận Tổng thể

1.  **Side Effect:** Dùng **Adapter Pattern** để biến I/O thành Managed Context. Không cấm, nhưng phải đi qua cổng kiểm soát.
2.  **Error:** Dùng **Contract-based Recovery**. Không chỉ "bắt lỗi", mà phải định nghĩa "chiến lược phản ứng" ngay trong Contract.

Điều này biến POP Engine thành một "Hệ miễn dịch" (Immune System) thông minh, biết khi nào nên chữa trị (Retry), khi nào nên cắt bỏ (Kill Process).
