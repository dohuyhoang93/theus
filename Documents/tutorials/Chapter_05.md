# Chương 5: ContextGuard & Zone Enforcement - Kỷ luật thép

Trong chương này, chúng ta sẽ đi sâu vào cơ chế bảo vệ của Theus v2: **Guard** và **Zone**.

## 1. Bất biến (Immutability) & Mở khóa (Unlocking)
Đây là nguyên tắc cốt lõi: **"Mọi thứ đều là Bất biến cho đến khi được Mở khóa."**

### Frozen Structures
Khi bạn đọc một List/Dict từ Context mà chỉ có quyền đọc (`inputs`):
- Engine trả về `FrozenList` hoặc `FrozenDict`.
- Các hàm sửa đổi (`append`, `pop`, `update`, `__setitem__`) đều bị vô hiệu hóa.
- Bạn chỉ có thể đọc (`get`, `len`, `iter`).

### Tracked Structures
Khi bạn có quyền ghi (`outputs`):
- Engine trả về `TrackedList` hoặc `TrackedDict`.
- Các thao tác sửa đổi được cho phép, nhưng chúng sẽ ghi log vào `Transaction Delta` chứ không sửa trực tiếp vào dữ liệu gốc ngay lập tức (Cơ chế Shadow).

## 2. Zone Enforcement (Cảnh sát Vùng)
Guard không chỉ kiểm tra quyền đọc/ghi, nó còn kiểm tra **Kiến trúc**.

### Input Guard
Trong hàm khởi tạo `ContextGuard`, Theus v2 kiểm tra tất cả các `inputs`:
```python
# Pseudo-code của Engine
for inp in inputs:
    if is_signal_zone(inp) or is_meta_zone(inp):
        raise ContractViolationError("Không được dùng Signal/Meta làm Input!")
```
Điều này ngăn chặn việc Process bị phụ thuộc vào các giá trị không bền vững.

### Output Guard
Ngược lại, bạn được phép ghi vào bất kỳ Zone nào (Data, Signal, Meta) miễn là bạn khai báo trong `outputs`.

## 3. Zero Trust Memory
Theus không tin vào "biến tạm".
```python
# Code xấu (Theus sẽ cảnh báo hoặc chặn)
my_list = ctx.domain.items
# ... làm gì đó lâu lắc ...
my_list.append(x) # Nguy hiểm! my_list có thể đã cũ (Stale)
```
Theus khuyến khích (và cơ chế Proxy ép buộc) bạn luôn truy cập qua `ctx.` để đảm bảo bạn đang tương tác với phiên bản mới nhất và hợp lệ nhất của dữ liệu trong Transaction hiện tại.

---
**Thực hành:**
Hãy thử "hack" Guard.
1. Khai báo `inputs=['domain.items']` (nhưng KHÔNG có outputs).
2. Trong hàm, thử gọi `ctx.domain.items.append(1)`.
3. Quan sát lỗi `FrozenListError` (hoặc tương tự) để thấy sự bảo vệ của Theus.