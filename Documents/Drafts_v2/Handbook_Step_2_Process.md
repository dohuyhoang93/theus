# Bước 2: Nghệ thuật của Hành động Thuần khiết (The Art of Pure Action)

---

## 2.1. Chuyện nhà Dev: "Hàm này làm gì? Làm tất cả!"

Bạn đang debug một lỗi sai lệch tồn kho. Bạn tìm thấy một hàm `process_order()` dài 500 dòng.
Nó làm gì?
1.  Tính tổng tiền, check hạng thành viên (Logic).
2.  Query DB để lấy tồn kho (Implicit IO).
3.  Modifiy thẳng vào biến global `TOTAL_REVENUE` (Global Mutation).

Đây là **"Spaghetti Function"**. Mọi thứ dính chùm vào nhau, không thể gỡ ra để test riêng lẻ.

---

## 2.2. Giải pháp POP: Process & Bản Hợp đồng (The Contract)

Trong POP, hàm không còn tự do. Nó bị ràng buộc bởi **Hợp đồng (Contract)**.

Decorator `@process` cho phép bạn khai báo:
1.  **`inputs`**: Tôi cần đọc gì?
2.  **`outputs`**: Tôi sẽ ghi gì?

Ngoài ra, POP V2 giới thiệu **Luật Kiểm Toán (Audit Rules)** nằm bên ngoài code.
*   **Process Logic**: "Nếu user VIP, giảm giá 10%". (Nghiệp vụ)
*   **Audit Logic (S/A/B/C)**: "Tổng tiền đơn hàng không bao giờ được âm". (An toàn)

---

## 2.3. Thực hành: Xử lý Đơn hàng

```python
from pop import process
from src.context import SystemContext

@process(
    name="validate_order",
    inputs=[
        'domain.user',      
        'domain.order',     
        'domain.warehouse'  
    ],
    outputs=[
        'domain.order.status',  
        'domain.order.error'    
    ]
)
def validate_order(ctx: SystemContext):
    user = ctx.domain.user
    order = ctx.domain.order
    
    # 1. Logic Nghiệp vụ (Business Logic)
    if user.balance < order.total_amount:
        ctx.domain.order.status = "REJECTED"
        return "FAILED"

    # 2. Logic cập nhật
    ctx.domain.order.status = "VALIDATED"
    return "OK"
```

---

## 2.4. Sự bảo vệ 2 Lớp (Dual Layer Protection)

Bạn có thể thắc mắc: *"Tại sao phải chia Process và Audit?"*

Hãy xem kịch bản sau: Bạn viết code giảm giá nhưng bị bug, tính ra số âm:
```python
order.total_amount = -100 # BUG!
```

1.  **Nếu không có Audit:** Hệ thống chuyển -100đ cho khách. Công ty lỗ vốn.
2.  **Có Audit (specs/audit_recipe.yaml):**
    ```yaml
    validate_order:
      output_rules:
        - target: domain.order.total_amount
          condition: min
          value: 0
          level: S  # STOP NGAY LẬP TỨC
    ```
    Engine sẽ chặn ngay khi Process vừa chạy xong, trước khi dữ liệu được commit. Bug bị bắt tại trận!

---

## 2.5. Sự thật về SDK: Cái gì bị chặn?

### **1. Contract Guard (Cứng)**
`ContextGuard` sẽ chặn đứng nếu bạn đọc/ghi vào biến Context chưa khai báo trong `inputs/outputs`.
*   *Cố tình ghi `domain.inventory` mà không khai báo Output?* -> **PermissionDenied**.

### **2. Audit Gate (Cứng)**
Kiểm tra giá trị đầu vào/đầu ra theo Luật S/A/B/C.
*   *Input vi phạm Level S?* -> **AuditInterlockError** (Process không được chạy).

### **3. Kỷ luật (Mềm)**
*   **Side Effects:** Bạn phải tự giác không gọi DB/API trong này (dùng Adapter).
*   **Determinism:** Không dùng `datetime.now()` bừa bãi.

---

## 2.6. Tổng kết Bước 2

*   Viết Process = Viết Logic thuần túy.
*   Khai báo Inputs/Outputs minh bạch.
*   Để phần "Bảo vệ an toàn" (Safety) cho Audit Recipe lo liệu.

**Thử thách:** Hãy viết một bug cố tình gán `total_amount = -1` và chạy thử xem `pop audit` có bắt được không nhé!
