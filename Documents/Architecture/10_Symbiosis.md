# Chương 10: Cộng sinh Đa mô hình (Symbiosis)

---

## 10.1. Đừng cực đoan hoá kiến trúc (No Dogma)

Theus không sinh ra để tiêu diệt OOP hay thay thế Clean Architecture. Theus sinh ra để giải quyết bài toán mà OOP làm chưa tốt: **Quản lý Dòng chảy (Flow Complexity).**

---

## 10.2. Phân vai: Vĩ mô và Vi mô (Macro vs Micro)

Để các mô hình sống chung hoà bình, chúng ta cần phân chia lãnh địa rõ ràng:

### **1. Theus quản lý Vĩ mô (Macro-Architecture)**
Theus chịu trách nhiệm về "Bộ xương sống" của ứng dụng:
*   Dữ liệu đi từ đâu đến đâu? (Workflow)
*   Bước nào chạy trước, bước nào chạy sau? (Orchestration)
*   Khi lỗi xảy ra thì xử lý thế nào? (Error Handling)

### **2. OOP quản lý Vi mô (Micro-Architecture)**
OOP chịu trách nhiệm về "Tế bào" của ứng dụng, nơi cần quản lý trạng thái nội tại chặt chẽ:
*   **Device Driver:** `CameraObject` giữ kết nối hardware, buffer hình ảnh.
*   **UI Widget:** `ButtonWidget` giữ trạng thái click, hover, color.
*   **Specific Algorithm:** Một class `KalmanFilter` giữ state ma trận nội tại.

> **Quy tắc vàng:** Process (Theus) là "Nhạc trưởng", Object (OOP) là "Nhạc công". Nhạc trưởng chỉ huy dòng nhạc, nhạc công chơi nhạc cụ của mình.

---

## 10.3. Chiến lược Thích ứng (Adaptation Strategy)

Làm sao để đưa code OOP cũ vào Theus?

### Wrapper Pattern (Bọc lại)
Đây là cách nhanh nhất.
*   Bạn có một class `LegacyPaymentService`.
*   Tạo một Process `process_payment(ctx)`.
*   Trong Process này, khởi tạo (hoặc lấy từ `env`) `LegacyPaymentService` và gọi hàm của nó.

### Injection Pattern (Tiêm vào)
Dùng cho Clean Architecture chuyên sâu.
*   Định nghĩa Interface trong `adapters/protocols.py`.
*   Implement Interface bằng Code cũ.
*   Config `env` để dùng implementation đó.

---

## 10.4. Kết luận
Đừng đập đi xây lại. Hãy dùng Theus để **kết nối** những gì bạn đang có.
Theus là lớp keo dính (Glue Layer) mạnh mẽ, biến những module rời rạc thành một dây chuyền sản xuất tự động.
