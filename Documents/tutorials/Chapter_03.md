# Chương 3: Process & Strict Contracts

Trong Theus v2, `@process` không chỉ là cú pháp, nó là một **Hợp đồng pháp lý (Legal Contract)** giữa code của bạn và Engine.

## 1. Giải phẫu một Contract
```python
@process(
    inputs=['domain.items'],          # Quyền ĐỌC
    outputs=['domain.total_value'],   # Quyền GHI
    errors=['ValueError']             # Các lỗi ĐƯỢC PHÉP xảy ra
)
```

## 2. Quy tắc Vàng: Không Input Signal
Đây là điểm khác biệt lớn nhất của v2.
**Quy tắc:** Bạn **KHÔNG ĐƯỢC** khai báo một biến `sig_` hoặc `cmd_` trong `inputs`.
- *Tại sao?* Vì Process phải là **Pure Logic** (Hàm thuần khiết). Logic của nó chỉ được phụ thuộc vào Data bền vững. Signal là thứ thoáng qua, nếu phụ thuộc vào nó, Process sẽ không thể Replay tin cậy được.
- *Làm sao để xử lý Signal?* Đó là việc của **Workflow Orchestrator** (Chương 11). Process chỉ nên xử lý kết quả của Signal (Data), chứ không phải bản thân Signal.

## 3. Viết Process đầu tiên
```python
from theus.contracts import process

@process(
    inputs=['domain.items'],           # Chỉ đọc items
    outputs=[
        'domain.items',                # Cần ghi items (append)
        'domain.total_value',          # Cần ghi total
        'domain.sig_restock_needed'    # Cần bật cờ báo động
    ],
    errors=['ValueError']
)
def add_product(ctx, name: str, price: int):
    if price < 0:
        raise ValueError("Giá không được âm!")
    
    # Thao tác nghiệp vụ
    product = {"name": name, "price": price}
    
    # ctx.domain.items giờ là TrackedList (được mở khóa vì có trong outputs)
    ctx.domain.items.append(product)
    
    # Cập nhật tổng
    ctx.domain.total_value += price
    
    # Bật Signal nếu cần (Output Signal là OK!)
    if len(ctx.domain.items) > 100:
        ctx.domain.sig_restock_needed = True
        
    return "Added"
```

## 4. Cơ chế Fail-Fast
Nếu bạn quên khai báo `domain.total_value` trong `outputs` mà cố tình `+= price`:
Theus v2 sẽ ném `ContractViolationError` ngay lập tức. Đây là tính năng **Zero Trust Memory** - không tin bất kỳ ai, kể cả chính người viết code.

---
**Thực hành:**
Viết process `add_product` như trên. Thử cố tình xóa dòng `outputs=['domain.total_value']` và chạy xem lỗi gì xảy ra.