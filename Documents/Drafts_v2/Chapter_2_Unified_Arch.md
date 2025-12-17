# Chương 2: Cộng sinh Đa mô hình: POP, OOP và Clean Architecture

---

## 2.1. Định vị POP trong bối cảnh Đa mô hình

POP không sinh ra để loại bỏ OOP hay thay thế Clean Architecture. POP giải quyết bài toán cốt lõi mà các mô hình truyền thống gặp khó khăn: **Quản lý sự phức tạp của Dòng chảy (Flow Complexity).**

Để xây dựng một hệ thống hoàn chỉnh và bền vững, kiến trúc sư cần áp dụng tư duy đa chiều, tận dụng sức mạnh riêng biệt của từng mô hình:

1.  **OOP (Object-Oriented Programming):** Tối ưu cho việc đóng gói trạng thái vật lý (`Device Driver`) và các thành phần giao diện (`UI Components`).
2.  **Clean Architecture:** Tối ưu cho việc thiết lập ranh giới bảo vệ (`Enterprise Boundaries`) trong các hệ thống quy mô lớn.
3.  **POP (Process-Oriented Programming):** Tối ưu cho việc điều phối logic nghiệp vụ (`Orchestration`) và quản lý luồng dữ liệu minh bạch.

---

## 2.2. Quy tắc Phối hợp 1: Dòng chảy & Cấu phần (POP + OOP)

Việc phân định ranh giới giữa POP và OOP không dựa trên sở thích cá nhân mà dựa trên tính chất kỹ thuật của đối tượng xử lý.

### 2.2.1. Lãnh địa của OOP (Component & State)
Sử dụng OOP khi cần mô hình hóa các thực thể có **trạng thái nội tại bất biến** hoặc **gắn liền với phần cứng/giao diện**.
*   **UI Widget:** Các đối tượng `Button`, `Window` cần quản lý trạng thái hiển thị và sự kiện input chuột/phím.
*   **Device Driver:** Các đối tượng `CameraDevice`, `SerialPort` cần quản lý tài nguyên hệ thống (connection handle, lock, buffer).

### 2.2.2. Lãnh địa của POP (Flow & Transformation)
Sử dụng POP khi cần mô tả **logic nghiệp vụ** hoặc **sự biến đổi dữ liệu**.
*   **Logic:** Các quy tắc nghiệp vụ ("Nếu A thì B") phải được hiện thực hóa thành `Process`.
*   **Data:** Dữ liệu đầu vào và đầu ra (Ảnh, Tọa độ, Thông tin đơn hàng) phải được đóng gói thành `Context`.

> **Cơ chế Cộng sinh:**
> `Process` (POP) đóng vai trò "Nhạc trưởng", điều phối các `Object` (OOP) thực thi nhiệm vụ cụ thể thông qua lớp Adapter.

---

## 2.3. Quy tắc Phối hợp 2: Thang đo Trừu tượng (POP + Clean Architecture)

Clean Architecture bảo vệ hệ thống thông qua các lớp Interface dày đặc (Dependency Inversion). POP tôn trọng nguyên tắc này nhưng đề xuất một **Thang đo linh hoạt (Abstraction Scale)** phù hợp với từng giai đoạn phát triển:

### Level 1: Duck Typing (Dynamic Link)
*   **Phạm vi áp dụng:** Startups, Prototype, Scripts xử lý dữ liệu, Game Logic.
*   **Đặc điểm:** `Env` là đối tượng tự do. Process gọi trực tiếp `env.camera.read()` mà không cần định nghĩa Interface trước.
*   **Lợi ích:** Tốc độ phát triển tối ưu, mã nguồn gọn nhẹ.

### Level 2: Strict Typing (Static Contract)
*   **Phạm vi áp dụng:** Sản phẩm thương mại, Hệ thống an toàn (Safety-critical), Dự án cần bảo trì dài hạn.
*   **Đặc điểm:** Sử dụng Python `Protocol` hoặc Rust `Trait` để định nghĩa `EnvContract`. Process chỉ tương tác với Contract, không phụ thuộc implementation cụ thể.
*   **Lợi ích:** Tăng cường an toàn kiểu dữ liệu (Type Safety), hỗ trợ refactoring mạnh mẽ từ IDE.

### Level 3: Enterprise Injection (Hard Boundaries)
*   **Phạm vi áp dụng:** Hệ thống Core Banking, Super-App với quy mô nhân sự lớn (>50 developers).
*   **Đặc điểm:** Áp dụng triệt để Clean Architecture. `Env` được inject thông qua Dependency Injection (DI) Container. Mọi thao tác I/O đều bị buộc phải tuân thủ Interface nghiêm ngặt.
*   **Lợi ích:** Module hóa tuyệt đối, đảm bảo tính độc lập cao giữa các team phát triển.

---

## 2.4. Tuyên ngôn Kiến trúc Hợp nhất (Unified Architecture)

Thay vì tư duy nhị nguyên ("Binary Thinking") buộc phải lựa chọn một mô hình duy nhất, POP khẳng định mô hình **Kiến trúc Hợp nhất**:

*   **POP là Kiến trúc Vĩ mô (Macro-Architecture):** Định hình "xương sống" của hệ thống là sự luân chuyển dữ liệu minh bạch qua các Process.
*   **OOP & Functional là Kiến trúc Vi mô (Micro-Architecture):** Cung cấp các công cụ và cấu trúc chi tiết để thực thi logic tại từng bước xử lý.

Sự kết hợp này tạo ra một hệ thống vừa có sự minh bạch của POP ở cấp độ tổng thể, vừa tận dụng được hệ sinh thái thư viện phong phú của OOP ở cấp độ chi tiết.

