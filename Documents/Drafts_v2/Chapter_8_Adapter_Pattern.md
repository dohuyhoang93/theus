# Chương 8: Adapter (Cổng giao tiếp I/O)

---

## 8.1. Triết lý thiết kế: Tại sao Adapter không phải là một "Layer"?

Trong kiến trúc Clean Architecture truyền thống, Adapter được xem là một tầng bao bọc (Wrapping Layer).
POP bác bỏ quan điểm này vì nó tạo ra sự phức tạp không cần thiết (Over-engineering).

> **POP quan niệm:** Adapter chỉ là một công cụ (Tool) nằm trong hộp đồ nghề của Process. Adapter là "Cổng giao tiếp câm" (Dumb Pipe).

**Lý do (Rationale):**
*   **Flow-First:** POP ưu tiên dòng chảy dữ liệu. Việc bắt dữ liệu phải "chui" qua nhiều tầng abstract (Interface → Abstract Class → Implementation) làm mờ đi bản chất của dòng chảy.
*   **Cognitive Load:** Mỗi tầng trừu tượng buộc não bộ Developer phải ghi nhớ thêm một mapping. POP muốn giảm tải bộ nhớ này.

---

## 8.2. Mô hình Environment: Thay thế Dependency Injection (DI)

Thay vì sử dụng DI Container phức tạp để "bơm" dependency vào Process, POP sử dụng mô hình **Environment Object**.

**Cấu trúc:**
```python
def process(ctx: Context, env: Environment) -> Context:
    # Explicit usage
    data = env.camera.capture()
```

**Tại sao lại chọn thiết kế này?**
1.  **Minh bạch (Transparency):** Nhìn vào hàm `process`, bạn thấy ngay nó nhận `env`. Không có magic "auto-wiring" ẩn đằng sau.
2.  **Dễ Debug:** `env` là một object thực, bạn có thể print nó ra để xem trạng thái kết nối của toàn bộ hệ thống.
3.  **Dễ Mock:** Khi test, chỉ cần truyền một `MockEnv` vào là xong. Không cần framework DI cồng kềnh.

---

## 8.3. Bốn Quy tắc Vàng & Lý do tồn tại

POP áp đặt 4 quy tắc cho Adapter. Dưới đây là giải thích chi tiết **Tại sao**:

### **Rule 1: Adapter không chứa Business Logic**
Adapter chỉ chuyển đổi dữ liệu thô (Raw bytes) ↔ Dữ liệu có cấu trúc (Structs).
*   **Tại sao:** Nếu Adapter chứa logic (ví dụ `if user.is_active`), logic đó sẽ bị chôn vùi trong tầng hạ tầng, khó tìm kiếm và khó test. Logic phải luôn nổi lên bề mặt (Process).

### **Rule 2: Adapter không trả về Context**
Adapter trả về `int`, `string`, `ImageFrame`, `UserObject`... nhưng không bao giờ trả về `DomainContext`.
*   **Tại sao:** Để Adapter có thể tái sử dụng cho nhiều dự án khác nhau (Reusability). Nếu Adapter buộc chặt vào `VisionContext`, nó không thể dùng cho dự án `AudioProcessing`.

### **Rule 3: Phân tách theo Tài nguyên Vật lý**
Adapter phải được tổ chức theo thiết bị: `CameraAdapter`, `RedisAdapter`.
*   **Tại sao:** Để quản lý Connection Pool và trạng thái phần cứng hiệu quả. Một Camera không thể vừa là "LoginService" vừa là "ImageProvider".

### **Rule 4: Gọi Tường minh (Explicit Invocation)**
Code phải viết rõ: `env.camera.capture()`.
*   **Tại sao:** Để khi đọc code (Code Review), ta thấy rõ điểm bắt đầu và kết thúc của một tác vụ I/O. Ẩn I/O sau các abstraction layer là nguồn gốc của các vấn đề hiệu năng khó tìm.

---

## 8.4. Tuyên ngôn Anti-OOP (The Anti-OOP Manifesto)

Spec Chapter 9 đưa ra một quan điểm gây tranh cãi nhưng hiệu quả: **"Nói KHÔNG với Interface và Abstract Class cho Adapter"**.

**Lập luận của POP:**

1.  **YAGNI (You Aren't Gonna Need It):**
    *   Bạn tạo `interface ICamera` vì nghĩ rằng "một ngày nào đó mình sẽ đổi từ OpenCV sang RealSense".
    *   **Thực tế:** Ngày đó hiếm khi đến. Và khi nó đến, việc sửa class `CameraAdapter` trực tiếp thường nhanh hơn việc duy trì một interface song song trong suốt 2 năm.

2.  **Premature Abstraction (Trừu tượng hóa sớm):**
    *   Tạo interface khi chưa có ít nhất 2 implementation thực tế là một sai lầm. Nó tạo ra những "khe hở" (leaky abstraction) mà code vẫn phải work-around.

3.  **Zero-Cost (Rust mentality):**
    *   Direct call luôn nhanh hơn Virtual Table dispatch (dù nhỏ). POP ưu tiên sự đơn giản và hiệu năng.

**Ngoại lệ:**
Bạn chỉ nên dùng Interface khi hệ thống thực sự cần hỗ trợ **đa driver đồng thời tại runtime** (ví dụ: Hệ thống hỗ trợ plugin driver động). Còn với logic nghiệp vụ thông thường => Class cụ thể (Concrete Class) là đủ.
