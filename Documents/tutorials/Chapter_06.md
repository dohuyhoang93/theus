# Chương 6: Transaction & Delta - Cỗ máy thời gian v2

Trong Theus v2, khái niệm Transaction được nâng cấp để đảm bảo tính toàn vẹn dữ liệu tuyệt đối (ACID-like) ngay trên bộ nhớ Python.

## 1. Hai chiến lược của Transaction
Theus sử dụng cách tiếp cận lai (Hybrid Approach) để tối ưu hiệu năng:

### 1.1. Optimistic Concurrency (Với Scalar: int, str, bool)
Khi bạn gán `ctx.domain.counter = 10`:
- **Hành động:** Theus ghi đè giá trị 10 vào Context thật **ngay lập tức** (In-place update).
- **Bảo hiểm:** Đồng thời, Theus ghi vào `DeltaLog`: *"Giá trị cũ của counter là 5"*.
- **Rollback:** Nếu lỗi, Theus đọc Log ngược từ dưới lên và khôi phục giá trị cũ.
- **Lợi ích:** Tốc độ cực nhanh cho các biến đơn giản.

### 1.2. Shadow Copy (Với Collection: list, dict)
Khi bạn sửa `ctx.domain.items`:
- **Hành động:** Theus tạo ra một bản sao (Shadow) của list đó.
- **Thao tác:** Mọi lệnh `append`, `pop` của bạn thực hiện trên cái Shadow này. List gốc không hề hay biết.
- **Commit:** Nếu thành công, Theus tráo đổi (swap) nội dung của Shadow vào List gốc.
- **Rollback:** Nếu lỗi, Shadow bị vứt bỏ. List gốc an toàn tuyệt đối.
- **Lợi ích:** An toàn cho cấu trúc dữ liệu phức tạp, tránh việc list bị sửa "nửa chừng".

## 2. Commit & Rollback Tự động
Bạn không bao giờ phải gọi `commit()` hay `rollback()` bằng tay. Engine lo việc đó.

```python
try:
    # 1. Start Tx
    # 2. Run Process
    # 3. Audit Output -> Nếu OK -> Commit
except Exception:
    # 4. Rollback
```

## 3. Signal Zone trong Transaction
Một điểm thú vị của Theus v2: **Signal cũng chịu ảnh hưởng của Transaction**.
- Nếu bạn bật cờ `sig_alarm = True`.
- Sau đó Process bị crash -> Rollback.
- Cờ `sig_alarm` sẽ tự động quay về `False` (hoặc giá trị cũ).
Điều này đảm bảo không bao giờ có "Báo động giả" từ một quy trình thất bại.

---
**Thực hành "Phá hoại" nâng cao:**
Trong process `add_product`:
1. Gán `sig_restock_needed = True`.
2. Append một item vào list.
3. Raise Exception ở cuối hàm.
4. Kiểm tra xem sau khi crash, `sig_restock_needed` có quay về `False` và item có biến mất khỏi list không?