# Bước 4: Kết nối Thế giới thực (Adapters & Environment)

---

## 4.1. Vùng Xanh và Vùng Đỏ

Khi bạn viết một con Robot AI:
*   **Vùng Xanh (Green Zone):** Logic an toàn. `if obstacle > 5m: speed = 10`.
*   **Vùng Đỏ (Red Zone):** Phần cứng. `camera.read()`, `motor.set_pwm()`.

Vùng Đỏ chứa đầy rủi ro: Mất kết nối, nhiễu tín hiệu, timeout.
**Nguyên tắc vàng của Theus:** Không bao giờ để Vùng Đỏ xâm nhập vào Vùng Xanh.

---

## 4.2. Adapter: Người lính biên phòng

Adapter là lớp code duy nhất được phép nói chuyện với phần cứng/API bên ngoài.

Hãy tạo file `adapters/camera.py`:

```python
# adapters/camera.py
import cv2

class CameraAdapter:
    def __init__(self, port=0):
        self.cap = cv2.VideoCapture(port)
        
    def read_frame(self):
        # Nơi duy nhất chứa code 'dơ' (IO-bound)
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame
```

**Quy tắc:** Adapter không bao giờ được import `theus`. Nó phải độc lập hoàn toàn.

---

## 4.3. Environment: Hộp đựng công cụ

Làm sao Process (ở `src/domain`) gọi được Camera (ở `adapters/`)?
Chúng ta dùng **Environment Object**.

File `adapters/env.py`:

```python
from dataclasses import dataclass
from .camera import CameraAdapter
from .robot_arm import RobotArmAdapter

@dataclass
class Environment:
    camera: CameraAdapter
    arm: RobotArmAdapter
```

---

## 4.4. Sử dụng trong Process

Khi bạn viết Process, hãy khai báo `env` trong tham số hàm. Theus sẽ tự động bơm (inject) Environment vào.

```python
# src/domain/vision.py

# [1] Khai báo Side-effect Contract
@process(
    inputs=[],
    outputs=["domain.camera.frame"],
    side_effects=["camera_read"] # Khai báo để Audit biết
)
def capture_image(ctx, env):  # <--- Theus tự truyền env vào đây
    
    # [2] Gọi Adapter tường minh
    frame = env.camera.read_frame()
    
    # [3] Lưu vào Context
    ctx.domain.camera.frame = frame
    return ctx.done()
```

---

## 4.5. Tại sao không dùng `import` trực tiếp?

*   **Mocking:** Khi chạy Unit Test, bạn có thể truyền `MockEnvironment(camera=FakeCamera())`. Nếu bạn `import adapters.camera` trực tiếp, bạn không thể mock được.
*   **Quản lý vòng đời:** Theus có thể tự động `connect()` và `disconnect()` tất cả adapter khi khởi động/tắt app.

---

## 4.6. Tổng kết

*   **Adapter:** Chuyên gia phần cứng.
*   **Environment:** Hộp đựng công cụ.
*   **Process:** Người thợ dùng công cụ để làm việc.

**Thử thách:** Viết một `SlackAdapter` và dùng nó để gửi tin nhắn cảnh báo khi Robot gặp vật cản.
