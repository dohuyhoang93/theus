# Chương 6: Tổ chức Mã nguồn (Theus Project Structure)

---

## 6.1. Nguyên tắc "Convention over Configuration"

Trong Theus, chúng tôi tin rằng sự sáng tạo nên dành cho thuật toán, còn cấu trúc thư mục thì nên nhàm chán (boring). Một dự án Theus luôn có cấu trúc dự đoán được, giúp bất kỳ ai trong team cũng có thể nhảy vào code ngay lập tức.

Lệnh khởi tạo chuẩn:
```bash
theus init my_project
```

---

## 6.2. Bản đồ Quy hoạch Đô thị (The Urban Plan)

Dự án Theus chia làm 3 vùng lãnh thổ rõ rệt:

```
my_project/
├── .theus/                 # [Hidden] Engine Metadata
├── specs/                  # [Law] Nơi chứa Luật lệ (YAML)
│   ├── context.yaml        # Data Schema
│   ├── workflow.yaml       # Execution Flow
│   └── audit.yaml          # Governance Rules
├── src/                    # [Citizens] Nơi chứa Code (Python)
│   ├── global/             # Layer 1: Global (Shared State)
│   ├── domain/             # Layer 2: Domain (Business Logic)
│   │   ├── vision.py       # -> Feature Module
│   │   └── robot.py
│   └── local/              # Layer 3: Local (Private Helper)
├── adapters/               # [Borders] Cửa khẩu giao tiếp
│   ├── camera.py           
│   └── database.py
└── tests/                  # [Inspection] Kiểm định
```

---

## 6.3. Giải phẫu chi tiết

### 1. `specs/` - Hiến pháp của Dự án
Đây là nơi đầu tiên bạn cần nhìn vào.
*   **Không chứa Code:** Chỉ chứa YAML/JSON.
*   **Vai trò:** Định nghĩa "Cái gì" (What).
*   **Quy tắc:** Mọi thay đổi về cấu trúc dữ liệu (`context.yaml`) hoặc luồng xử lý (`workflow.yaml`) đều phải được review kỹ lưỡng tại đây.

### 2. `src/` - Cư dân của Dự án
Code logic được tổ chức theo **Layer** (Tầng), không phải theo loại file.
*   **`src/global`:** Chứa các config dùng chung, consts.
*   **`src/domain`:** Chứa logic nghiệp vụ chính. Mỗi file (ví dụ `vision.py`) nên chứa trọn vẹn cả Context Definition (`class VisionState`) và Process (`def detect_face`) liên quan. -> **Tính cô lập (Colocation).**
*   **`src/local`:** Chứa các hàm tiện ích nhỏ, tính toán thuần túy, không state.

### 3. `adapters/` - Biên giới
Nơi duy nhất được phép import các thư viện I/O (Opencv, SQLDriver, Requests).
*   Quy tắc: Adapter không được chứa logic nghiệp vụ. Nó chỉ chuyển đổi data thô thành data sạch.

---

## 6.4. Module hóa theo Theus (Theus Modularity)

Khác với Django (chia theo App) hay Flask (chia theo Blueprint), Theus chia theo **Feature Vertical**.

Ví dụ file `src/domain/vision.py`:

```python
# [1] Context Definition (Data)
@dataclass
class VisionContext:
    last_frame: np.ndarray = None
    face_count: int = 0

# [2] Process Implementation (Logic)
@process(inputs=['domain.vision'], outputs=['domain.vision'])
def detect_faces(ctx):
    # logic...
```
**Lợi ích:** Data và Logic nằm cùng một chỗ. Thay đổi logic (`detect_faces`) thường kéo theo thay đổi data (`face_count`), nên để chung giúp giảm context switching.

---

## 6.5. Registry & Loading (Cơ chế Wiring)

Làm sao Engine biết `vision.py` tồn tại?

Theus sử dụng cơ chế **Auto-Discovery**:
1.  Khi chạy `theus run`, Engine quét thư mục `src/`.
2.  Nó import tất cả các file `.py`.
3.  Decorator `@process` tự động đăng ký hàm vào **Global Registry**.
4.  Engine đọc `workflow.yaml`, khớp tên string (`"detect_faces"`) với Registry để thực thi.

> **Lưu ý:** Bạn không cần file `main.py` để "nối dây" thủ công. Theus lo việc đó.

---

## 6.6. Chiến lược Kiểm thử (Testing Strategy)

### 1. Unit Test (Pure Logic)
Vì Process là hàm thuần túy (hoặc gần thuần túy), việc test cực dễ:
```python
def test_detect_face():
    # Setup
    ctx = MockContext(vision=VisionContext(last_frame=fake_img))
    
    # Act
    detect_faces(ctx)
    
    # Assert
    assert ctx.domain.vision.face_count == 1
```

### 2. Integration Test (Simulated Flow)
Dùng `specs/workflow.test.yaml`. Chạy toàn bộ luồng với Adapter giả (Mock Adapter).

---

## 6.7. Các Dấu hiệu Sai lầm (Anti-Patterns)

1.  **Logic trong Adapter:** `adapters/camera.py` lại đi check `if user.is_vip`. Sai! Adapter chỉ chụp ảnh. Logic VIP phải ở `src/domain`.
2.  **Config phân tán:** Hardcode config trong file python thay vì để trong `specs/context.yaml`.
3.  **God Object:** Dồn hết logic vào `src/domain/core.py`. Hãy chia nhỏ theo feature (`vision.py`, `movement.py`).
