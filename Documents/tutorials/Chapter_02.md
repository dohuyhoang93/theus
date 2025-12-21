# Chương 2: Thiết kế Context 3 Trục (The 3-Axis Context)

Trong Theus v2, Context không chỉ là một cái túi đựng dữ liệu. Nó là một cấu trúc không gian 3 chiều giúp Engine hiểu và bảo vệ dữ liệu của bạn.

## 1. Tư duy "Hybrid Context Zones"
Thay vì bắt bạn viết `ctx.domain.data.user_id` (quá dài dòng), Theus v2 dùng cơ chế **Hybrid**. Bạn viết phẳng (`ctx.domain.user_id`), nhưng Engine sẽ âm thầm phân loại nó vào các **Zone** dựa trên quy ước đặt tên (Naming Convention) hoặc Schema.

| Zone | Prefix | Tính chất | Cơ chế bảo vệ |
| :--- | :--- | :--- | :--- |
| **DATA** | (Không có) | Tài sản nghiệp vụ (Asset). Bền vững. | Transaction Full, Replay Strict. |
| **SIGNAL** | `sig_`, `cmd_` | Sự kiện/Lệnh (Event). Tự hủy. | Transaction Reset, Không Replay. |
| **META** | `meta_` | Thông tin phụ (Debug). | Read-only (thường là vậy). |

## 2. Thiết kế bằng Dataclass
Chúng ta vẫn dùng `dataclass`, nhưng cần tuân thủ quy ước Zone.

```python
from dataclasses import dataclass, field
from theus.context import BaseSystemContext

# 1. Định nghĩa Domain (Nghiệp vụ)
@dataclass
class WarehouseDomain:
    # --- DATA ZONE (Tài sản) ---
    items: list = field(default_factory=list)
    total_value: int = 0
    
    # --- SIGNAL ZONE (Điều khiển) ---
    sig_restock_needed: bool = False  # Cờ báo cần nhập hàng
    cmd_stop_robot: bool = False      # Lệnh dừng khẩn cấp

# 2. Định nghĩa Global (Cấu hình)
@dataclass
class WarehouseConfig:
    max_capacity: int = 1000
    warehouse_name: str = "Kho Tổng"

# 3. Gắn vào System Context
@dataclass
class WarehouseContext(BaseSystemContext):
    domain: WarehouseDomain = field(default_factory=WarehouseDomain)
    # Global đã có sẵn, ta sẽ gán instance của WarehouseConfig vào sau
```

## 3. Tại sao phân vùng lại quan trọng?
Khi bạn chạy **Replay (Tua lại lỗi)**:
- Theus sẽ khôi phục chính xác `items` và `total_value` (Data Zone).
- Theus sẽ **BỎ QUA** `sig_restock_needed` (Signal Zone) vì đó là nhiễu của quá khứ.
Điều này đảm bảo tính **Determinism** (Xác định) - Chạy 100 lần kết quả y hệt nhau.

## 4. Cơ chế Khóa (Locked Context)
Theus bảo vệ Context bằng `LockManager`.

### 4.1. Trạng thái Mặc định: LOCKED
Ngay khi bạn khởi tạo `Engine(ctx)`, Context sẽ chuyển sang trạng thái **KHÓA**.
Nếu bạn cố tình viết code sửa đổi từ bên ngoài (External Mutation):
```python
# Code nằm ngoài @process
def hack_system(ctx):
    ctx.domain.total_value = 9999 # -> Raises ContextLockedError!
```
Hệ thống sẽ ném lỗi để ngăn chặn các thay đổi trạng thái không thể truy vết (Untraceable Mutations).

### 4.2. Cách sửa hợp lệ: `engine.edit()`
Trong các trường hợp đặc biệt (như Unit Test, Setup dữ liệu ban đầu), bạn cần sửa Context mà không muốn viết Process. Theus cung cấp "Chìa khóa vạn năng":

```python
# Mở khóa tạm thời trong khối with
with engine.edit() as safe_ctx:
    safe_ctx.domain.total_value = 100
    safe_ctx.domain.items.append("Setup Item")
# Ra khỏi khối with -> Tự động KHÓA lại ngay.
```

---
**Thực hành:**
Tạo file `warehouse_ctx.py`. Định nghĩa Context như trên. 
Thử viết một hàm main, khởi tạo Engine, sau đó cố tình gán `ctx.domain.total_value = 1` mà không dùng `engine.edit()`. Quan sát lỗi `ContextLockedError`.
