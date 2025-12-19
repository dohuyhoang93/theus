# Chương 8: Adapter & Environment (Giao tiếp Ngoại vi)

---

## 8.1. Triết lý "Biên Giới Cứng" (Hard Borders)

Trong Theus, thế giới được chia làm hai nửa:
1.  **Vùng Xanh (Green Zone):** Logic thuần túy, an toàn, có thể replay. (Nằm trong `src/domain`).
2.  **Vùng Đỏ (Red Zone):** I/O, Side-effects, không thể đoán trước. (Nằm trong `adapters/`).

**Adapter** chính là "Cửa khẩu" nơi dữ liệu từ Vùng Đỏ nhập cảnh vào Vùng Xanh.

---

## 8.2. Environment Object (`env`)

Thay vì Dependency Injection (DI) phức tạp, Theus sử dụng mô hình **Environment Object**.
Hệ thống sẽ khởi tạo tất cả các adapters khi startup, gom chúng vào một object duy nhất là `env`, và truyền object này vào từng Process.

### Cấu trúc
```python
# adapters/env.py
@dataclass
class Environment:
    camera: CameraAdapter
    database: DatabaseAdapter
    mqtt: MqttAdapter

# src/domain/vision.py
@process(side_effects=["camera"])
def capture(ctx, env: Environment):
    # [Explicit Call]
    img = env.camera.read_last_frame()
    ctx.domain.vision.last_frame = img
```

**Tại sao lại chọn thiết kế này?**
1.  **Zero Magic:** Không có `@Inject`, không có Container ảo diệu. `env` là một biến bình thường.
2.  **Dễ Mock:** Khi test, chỉ cần truyền `MockEnv` là xong.

---

## 8.3. Bốn Quy tắc Vàng cho Adapter

### **Rule 1: Quy tắc "Ống Nước Câm" (Dumb Pipe)**
Adapter chỉ được phép làm nhiệm vụ vận chuyển dữ liệu.
*   **Sai:** Adapter kiểm tra `if user.age < 18`. (Đây là Business Logic).
*   **Đúng:** Adapter lấy `age` từ DB và trả về nguyên vẹn.

### **Rule 2: Không trả về Context**
Adapter trả về dữ liệu nguyên thủy (`dict`, `object`, `list`). Không bao giờ được phép trả về hoặc sửa đổi `DomainContext`.
*   *Lý do:* Để Adapter tái sử dụng được (Decoupling).

### **Rule 3: Phân tách theo Tài nguyên Vật lý**
Mỗi Adapter tương ứng với một "thứ" bên ngoài: `RedisAdapter`, `CameraAdapter`, `GPTAdapter`. Đừng tạo `UserAdapter` (trừu tượng).

### **Rule 4: Gọi Tường minh**
Không bao giờ được giấu Adapter sau một hàm logic. Phải luôn thấy `env.adapter_name.method()` trong code của Process.

---

## 8.4. Interface hay Concrete Class?

Spec Chapter 9 đưa ra quan điểm: **"Pragmatic Abstraction"**.

*   **Với dự án nhỏ/vừa:** Dùng Concrete Class (`class PostgresAdapter`). Đừng tạo Interface `IDatabase` trừ khi bạn thực sự cần đổi sang MySQL vào tuần sau.
*   **Với dự án lớn (Enterprise):** Dùng `Python Protocol` để định nghĩa Interface. Điều này giúp `mypy` bắt lỗi tốt hơn mà không cần thừa kế rườm rà.

### Ví dụ dùng Protocol (Theus Standard)
```python
# adapters/protocols.py
class CameraProtocol(Protocol):
    def read(self) -> np.ndarray: ...

# adapters/real_camera.py
class RealCamera:
    def read(self): return cv2.read()

# modules/vision.py
def process(ctx, env):
    # env.camera: CameraProtocol
    env.camera.read()
```
Cách này cân bằng giữa Tốc độ và Sự chặt chẽ.
