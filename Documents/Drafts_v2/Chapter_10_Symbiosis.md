# Chương 10: Cộng sinh Đa mô hình (Symbiosis)

---

## 10.1. Đừng cực đoan hoá kiến trúc (No Dogma)

Một sai lầm phổ biến khi tiếp cận kiến trúc mới là tâm lý "đập đi xây lại" (All or Nothing).
"Nếu dùng POP thì phải bỏ hết Class", "Nếu dùng Class thì không phải là POP".

> **Sự thật:** POP không sinh ra để tiêu diệt OOP hay thay thế Clean Architecture. POP sinh ra để giải quyết bài toán mà OOP làm chưa tốt: **Quản lý Dòng chảy (Flow Complexity).**

---

## 10.2. Phân vai: Vĩ mô và Vi mô (Macro vs Micro)

Để các mô hình sống chung hoà bình, chúng ta cần phân chia lãnh địa rõ ràng:

### **1. POP quản lý Vĩ mô (Macro-Architecture)**
POP chịu trách nhiệm về "Bộ xương sống" của ứng dụng:
*   Dữ liệu đi từ đâu đến đâu? (Workflow)
*   Bước nào chạy trước, bước nào chạy sau? (Orchestration)
*   Khi lỗi xảy ra thì xử lý thế nào? (Error Handling)

### **2. OOP quản lý Vi mô (Micro-Architecture)**
OOP chịu trách nhiệm về "Tế bào" của ứng dụng, nơi cần quản lý trạng thái nội tại chặt chẽ:
*   **Device Driver:** `CameraObject` giữ kết nối hardware, buffer hình ảnh.
*   **UI Widget:** `ButtonWidget` giữ trạng thái click, hover, color.
*   **Specific Algorithm:** Một class `KalmanFilter` giữ state ma trận nội tại.

> **Quy tắc vàng:** Process (POP) là "Nhạc trưởng", Object (OOP) là "Nhạc công". Nhạc trưởng chỉ huy dòng nhạc, nhạc công chơi nhạc cụ của mình.

---

## 10.3. Thang đo Trừu tượng (Abstraction Scale)

Clean Architecture bảo vệ hệ thống bằng các lớp Interface và Dependency Inversion. POP tôn trọng điều này nhưng đề xuất một **Thang đo linh hoạt** tuỳ theo quy mô dự án:

### **Level 1: Duck Typing (Dynamic - Startup Mode)**
*   **Dành cho:** Prototype, Script, Game Logic, dự án < 3 tháng.
*   **Cách làm:** Process gọi trực tiếp `env.camera.read()` mà không cần Interface.
*   **Lợi ích:** Tốc độ phát triển cực nhanh. Code "mềm" và linh hoạt.

### **Level 2: Strict Typing (Safety - Standard Mode)**
*   **Dành cho:** Sản phẩm thương mại, Hệ thống nhúng an toàn, dự án dài hơi.
*   **Cách làm:** Sử dụng `Protocol` (Python) hoặc `Trait` (Rust) để định nghĩa Contract cho `Env`. Process chỉ biết đến Contract.
*   **Lợi ích:** IDE hỗ trợ tốt (Auto-complete), dễ dàng thay thế Mock Driver khi test.

### **Level 3: Enterprise Injection (Enterprise Mode)**
*   **Dành cho:** Core Banking, Super App, dự án > 50 người.
*   **Cách làm:** Áp dụng Clean Architecture triệt để. Dùng Dependency Injection Container để bơm Implementation vào Interface. Ranh giới cực kỳ cứng.
*   **Lợi ích:** Module hoá tuyệt đối, team lớn không dẫm chân nhau.

---

## 10.4. Tuyên ngôn Kiến trúc Hợp nhất

Chúng ta không cần chọn phe.
*   Dùng **POP** để nhìn thấy bức tranh toàn cảnh (Dòng chảy).
*   Dùng **OOP** để đóng gói các chi tiết kỹ thuật phức tạp (Driver, UI).
*   Dùng **Clean Architecture** để bảo vệ ranh giới khi hệ thống phình to.

Đó là con đường "Trung đạo", nơi chúng ta tận dụng sức mạnh của mọi công cụ để tạo ra phần mềm tốt nhất.
