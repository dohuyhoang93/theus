# Bước 2: Thiết kế Process (Hành động chuẩn mực)

---

## 2.1. Triết lý "Hộp Đen Trong Suốt"

Một Process trong Theus giống như một linh kiện điện tử:
1.  **Chân cắm vào (Inputs):** Rõ ràng, cố định.
2.  **Chân cắm ra (Outputs):** Đo lường được.
3.  **Lõi (Logic):** Xử lý thuần túy.

Khác với hàm Python thông thường (có thể gọi `global`, `print`, `db` lung tung), Theus Process bị ràng buộc bởi **Hợp đồng (Contract)**.

---

## 2.2. Viết Process đầu tiên

Hãy mở file `src/domain/vision.py` và viết một logic kiểm tra chất lượng ảnh.

```python
from theus import process

# [1] Input Contract: Chỉ đọc những gì cần thiết
# [2] Output Contract: Chỉ ghi những gì đã hứa
# [3] Error Contract: Khai báo lỗi nghiệp vụ
@process(
    inputs=["domain.camera.frame"],
    outputs=["domain.vision.is_blur", "domain.vision.brightness"],
    errors=["FRAME_CORRUPTED"]
)
def check_image_quality(ctx):
    # Lấy dữ liệu từ Context (Read-Only)
    frame = ctx.domain.camera.frame
    
    if frame is None:
        # Trả về lỗi nghiệp vụ (Không phải Exception!)
        return ctx.fail("FRAME_CORRUPTED")
        
    # Xử lý logic
    is_blur = detect_blur(frame)
    brightness = calculate_brightness(frame)
    
    # Ghi dữ liệu vào Context (Write-Only)
    ctx.domain.vision.is_blur = is_blur
    ctx.domain.vision.brightness = brightness
    
    # Trả về thành công
    return ctx.done()
```

---

## 2.3. Ba Quy tắc Vàng của Process

### 1. Pure Function (Hàm thuần túy)
Process **không được** lưu trạng thái vào biến `self` hay `global`.
Mọi trạng thái phải nằm trên Context.
*   *Tại sao?* Để hệ thống có thể Restart, Retry, và Replay bất cứ lúc nào.

### 2. Explicit Dependencies (Phụ thuộc rạch ròi)
Nếu bạn cần dùng `cv2` hay `numpy`, hãy import nó ở đầu file.
Nếu bạn cần nối Database, hãy dùng Adapter (xem Step 4). Tuyệt đối không tạo connection lén lút trong hàm.

### 3. Fail Fast (Lỗi là dừng)
Đừng `try/catch` rộng để giấu lỗi. Nếu có lỗi không lường trước (ví dụ: chia cho 0), hãy để nó crash. Theus sẽ bắt (`catch`) ở tầng ngoài cùng và rollback transaction an toàn.

---

### 2.2. Giải phẫu một Process
Process là đơn vị logic nhỏ nhất. Nó tuân thủ **Context Contract**:

```python
@process(
    # [EXPLICIT DATA] Phải khai báo trong src/context.py
    inputs=["domain.user_id", "global.config.time_zone"], 
    outputs=["domain.user_profile"],
    
    # [METADATA TAGS] Chỉ là nhãn hành vi, không phải class
    side_effects=["Database", "Log"], 
    errors=["UserNotFound"]
)
def fetch_user_profile(ctx):
    # [IMPLICIT LOCAL] Biến cục bộ trong hàm là Local Context
    user_id = ctx.domain.user_id 
    
    # Logic...
    return ctx.done()
```

> **Lưu ý quan trọng:**
> *   **System/Global/Domain:** Là các Cấu trúc Dữ liệu (Class) bạn phải định nghĩa.
> *   **Local:** Là vùng nhớ tạm của hàm (Variable), không cần định nghĩa.
> *   **Side-Effect/Error:** Là Metadata để Audit, không phải biến.

## 2.4. Unit Test cho Process

Vì Process là hàm thuần túy, việc test cực kỳ "sướng":

```python
def test_check_image_quality():
    # 1. Setup Mock Context
    ctx = MockContext()
    ctx.domain.camera.frame = create_black_image()
    
    # 2. Run Process
    result = check_image_quality(ctx)
    
    # 3. Assert
    assert result.is_success
    assert ctx.domain.vision.brightness == 0
```

Bạn không cần Database, không cần Camera thật. Chỉ cần dữ liệu giả.

---

## 2.5. Tổng kết

*   Dùng `@process` để biến hàm thường thành linh kiện Theus.
*   Khai báo `inputs`/`outputs` để Theus bảo vệ bạn (ContextGuard).
*   Test logic nghiệp vụ độc lập với hệ thống.
