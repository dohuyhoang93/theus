# Chương 7: Cạm bẫy Mutable & Cấu trúc Tracked

Làm việc với List và Dict trong môi trường Transaction là nơi dễ xảy ra lỗi nhất ("Gotcha"). Chương này giúp bạn tránh những cái bẫy đó.

## 1. TrackedList & TrackedDict
Khi bạn truy cập `ctx.domain.items` (được khai báo trong `outputs`), Theus không trả về list thường. Nó trả về `TrackedList`.
Đây là một "Lớp vỏ thông minh" (Smart Wrapper) bao bọc lấy Shadow Copy.

**Quy tắc:** Đừng bao giờ `type(ctx.domain.items) == list`. Hãy dùng `isinstance(..., list)`.

## 2. Hiểm họa "Zombie Proxy" (Xác sống)
Đây là lỗi phổ biến nhất của người mới.

```python
# Code SAI
my_temp = ctx.domain.items  # Lưu tham chiếu TrackedList ra biến ngoài
# ... Process kết thúc, Transaction Commit/Rollback ...

# Ở một Process khác hoặc lần chạy sau:
my_temp.append("Ghost") # LỖI!
```

**Tại sao?**
Khi Transaction kết thúc, cái Shadow Copy mà `my_temp` đang nắm giữ đã:
- Hoặc được merge vào gốc (Commit).
- Hoặc bị hủy (Rollback).
Biến `my_temp` giờ đây trỏ vào hư vô hoặc dữ liệu cũ (Stale Data). Theus v2 có cơ chế phát hiện và ngăn chặn việc dùng Zombie Proxy, nhưng tốt nhất là đừng tạo ra chúng.

**Lời khuyên:** Luôn truy cập trực tiếp `ctx.domain.items` khi cần dùng. Đừng cache nó ra biến cục bộ quá lâu.

## 3. FrozenList (Bất biến)
Nếu bạn chỉ `inputs=['domain.items']` (không output):
- Bạn nhận được `FrozenList`.
- `FrozenList` vẫn chia sẻ dữ liệu với list gốc (để tiết kiệm RAM), nhưng nó chặn mọi API ghi.
- Đây là cách Theus tiết kiệm hiệu năng: Không cần Copy nếu bạn chỉ đọc.

---
**Thực hành:**
Thử tạo một biến toàn cục `G_CACHE = []` trong file python.
Trong process 1: `G_CACHE = ctx.domain.items`.
Sau khi process 1 chạy xong, thử truy cập `G_CACHE` ở bên ngoài. Quan sát xem dữ liệu trong đó còn đúng với `sys_ctx.domain.items` hiện tại không?