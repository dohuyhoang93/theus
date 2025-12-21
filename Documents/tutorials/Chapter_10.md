# Chương 10: Dual-Thresholds - Sự khoan dung của hệ thống

Hệ thống thực tế luôn có nhiễu (Noise). Theus v2 cho phép bạn cấu hình sự "Khoan dung" (Tolerance) thông qua cơ chế Threshold.

## 1. Cơ chế Threshold hoạt động thế nào?
Mỗi Rule có một bộ đếm riêng (Counter) trong `AuditTracker`.
- **min_threshold:** Ngưỡng bắt đầu cảnh báo (Yellow).
- **max_threshold:** Ngưỡng kích hoạt hình phạt (Red Action - S/A/B).

**Ví dụ:** `max_threshold: 3`.
- Lần 1 lỗi: Cho qua (hoặc Warn nếu >= min).
- Lần 2 lỗi: Cho qua.
- Lần 3 lỗi: **BÙM!** Kích hoạt Level (ví dụ Block).
- Sau khi "BÙM", bộ đếm reset về 0.

## 2. Lưu ý quan trọng: Tích lũy lỗi (Error Accumulation)
Mặc định trong Theus v2, bộ đếm **KHÔNG RESET KHI THÀNH CÔNG**.
Đây là tính năng, không phải lỗi.
- Nó giúp phát hiện các hệ thống chập chờn (Flaky).
- Nếu cứ 10 lần chạy thì có 1 lần lỗi -> Sau 30 lần chạy, bạn sẽ bị chặn (vì tích đủ 3 lỗi).
- Nếu bạn muốn reset? Bạn phải restart Engine hoặc cấu hình lại Tracker (tính năng nâng cao).

## 3. Ứng dụng thực tế
- **Rate Limiting:** Cho phép vi phạm tốc độ 5 lần trước khi chặn IP.
- **Sensor Glitch:** Cảm biến nhiệt độ đôi khi nhảy sai 1 giá trị. Đừng dừng máy ngay. Hãy đợi 3 giá trị sai liên tiếp rồi hãy dừng.

---
**Thực hành:**
Cấu hình `max_threshold: 3` cho luật `price >= 0`.
Thử gọi `add_product` với giá âm liên tiếp.
Quan sát: Lần 1 OK (Warn). Lần 2 OK (Warn). Lần 3 -> Exception!
Sau đó gọi tiếp Lần 4 -> Lại OK (Warn) vì bộ đếm đã reset.