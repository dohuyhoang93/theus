# Chương 4: TheusEngine - Vận hành Cỗ máy

TheusEngine v2 là một cỗ máy phức tạp với nhiều tầng bảo vệ. Hiểu được luồng chạy của nó giúp bạn debug dễ dàng hơn.

## 1. Khởi tạo Engine chuẩn v2
```python
from theus.engine import TheusEngine
from warehouse_ctx import WarehouseContext, WarehouseConfig, WarehouseDomain

# Setup Context
config = WarehouseConfig(max_capacity=500)
domain = WarehouseDomain()
sys_ctx = WarehouseContext(global_ctx=config, domain_ctx=domain)

# Khởi tạo Engine (Strict Mode mặc định nên bật trong Dev)
engine = TheusEngine(sys_ctx, strict_mode=True)
```

## 2. Luồng thực thi (The Execution Pipeline)
Khi bạn gọi `engine.run_process("add_product", name="TV", price=500)`, điều gì thực sự xảy ra?

1.  **Audit Input Gate:**
    - Engine gọi `ContextAuditor`.
    - Kiểm tra xem tham số đầu vào (`name`, `price`) có vi phạm luật Audit nào không (nếu có Recipe).
    - Nếu vi phạm `Level S` -> **Dừng ngay**.

2.  **Context Locking:**
    - Nếu hệ thống đang chạy đa luồng, Engine sẽ **Lock** toàn bộ Context để đảm bảo Process này được chạy độc quyền (Atomic).

3.  **Transaction Start:**
    - Engine chụp ảnh trạng thái hiện tại (hoặc chuẩn bị cơ chế Shadow Copy).

4.  **Guard Injection:**
    - Engine tạo ra một `ContextGuard` bao bọc lấy Context thật.
    - Cấp phát chìa khóa (Permissions) dựa trên Contract của Process.

5.  **Execution:**
    - Code của bạn chạy. Mọi thay đổi diễn ra trên bản nháp (Shadow/Delta).

6.  **Audit Output Gate:**
    - Process chạy xong, nhưng chưa Commit.
    - Engine kiểm tra kết quả trên bản nháp. Ví dụ: "Sau khi cộng, `total_value` có vượt quá 1 tỷ không?".
    - Nếu vi phạm -> **Rollback**.

7.  **Commit/Rollback:**
    - Nếu mọi thứ OK -> Ghi bản nháp vào Context thật (Commit).
    - Mở khóa (Unlock).

## 3. Chạy thử
```python
engine.register_process("add_product", add_product)

try:
    engine.run_process("add_product", name="Iphone", price=1000)
    print("Success!", sys_ctx.domain.items)
except Exception as e:
    print(f"Failed: {e}")
```

---
**Thực hành:**
Viết file `main.py`. Chạy thử process. Thử in ra `sys_ctx.domain.sig_restock_needed` sau khi chạy để xem Signal có được cập nhật không.