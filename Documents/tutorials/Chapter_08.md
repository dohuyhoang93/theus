# Chương 8: Audit System V2 - Industrial Policy Enforcement

Quên những câu lệnh `if/else` kiểm tra dữ liệu đi. Theus v2 mang đến hệ thống Audit chuẩn Công nghiệp.

## 1. Audit Recipe & RuleSpec
Mọi quy tắc kiểm tra được định nghĩa trong file YAML (Audit Recipe) và nạp vào Engine khi khởi động.

### Cấu trúc mới của Rule
Một Rule (Quy tắc) giờ đây phức tạp hơn nhiều:
- **Condition:** `min`, `max`, `eq`, `neq`, `max_len`, `min_len`.
- **Thresholds:** `min_threshold` (Cảnh báo) vs `max_threshold` (Hành động).
- **Level:** `S`, `A`, `B`, `C`.

## 2. Ví dụ file `audit_recipe.yaml`
```yaml
process_recipes:
  add_product:
    inputs:
      - field: "price"
        min: 0
        level: "B"  # Chặn nếu giá âm (Block)
        
    outputs:
      - field: "domain.total_value"
        max: 1000000000  # Max 1 tỷ
        level: "S"       # Dừng hệ thống nếu vượt (Safety)
        message: "Nguy hiểm! Tổng giá trị kho quá lớn."
        
      - field: "domain.items"
        max_len: 1000
        level: "A"       # Abort process nếu quá 1000 món
        min_threshold: 1 # Cảnh báo ngay lần đầu
        max_threshold: 3 # Chặn ở lần thứ 3 liên tiếp
```

## 3. Cách nạp Recipe vào Engine
```python
from theus.config import ConfigFactory

# 1. Load Recipe từ YAML
recipe = ConfigFactory.load_recipe("audit_recipe.yaml")

# 2. Inject vào Engine
engine = TheusEngine(sys_ctx, audit_recipe=recipe)
```

## 4. Input Gate & Output Gate
- **Input Gate:** Kiểm tra tham số hàm (`price`, `name`) *trước khi* Process chạy. Giúp tiết kiệm tài nguyên (Fail Fast).
- **Output Gate:** Kiểm tra Context (`domain.total_value`) *sau khi* Process chạy (trên Shadow) nhưng *trước khi* Commit.

---
**Thực hành:**
Tạo file `audit.yaml`. Cấu hình luật: `price` phải >= 10. `domain.items` max_len = 5.
Chạy process thêm sản phẩm giá 5 đồng -> Xem bị chặn ngay từ Input Gate (Block).
Chạy process thêm đến món thứ 6 -> Xem bị chặn ở Output Gate (Abort).