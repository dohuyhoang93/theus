# Chương 12: Zone Architecture - Kiến trúc sạch v2

Chương này tổng hợp lại toàn bộ kiến thức về Zone để bạn xây dựng hệ thống lớn (Scalable System).

## 1. Ba vùng đất thiêng (The Holy Trinity)

| Zone | Prefix | Định nghĩa | Quy tắc sống còn |
| :--- | :--- | :--- | :--- |
| **DATA** | (None) | **Single Source of Truth.** Tài sản nghiệp vụ. | Luôn được Replay. Phải được bảo vệ bằng Audit nghiêm ngặt. |
| **SIGNAL** | `sig_` | **Control Flow.** Sự kiện, Lệnh, Cờ hiệu. | Không bao giờ dùng làm Input cho Data Process. Tự hủy sau khi dùng. |
| **META** | `meta_` | **Observability.** Log, Trace, Debug info. | Không ảnh hưởng đến Logic nghiệp vụ. Thường Read-only hoặc Write-once. |

## 2. Quy tắc biên giới (Boundaries)
Engine v2 thực thi quy tắc biên giới cứng rắn:

- **Rule 1: Data Isolation.** Process tính toán Data chỉ nên phụ thuộc vào Data. Output của nó cũng nên là Data.
- **Rule 2: Signal Trigger.** Signal chỉ nên xuất hiện ở Output của Process để báo hiệu cho Orchestrator. (Hoặc Input của các Process thuần túy về điều khiển/UI).
- **Rule 3: Meta Transparency.** Meta có thể được ghi ở bất cứ đâu (để đo thời gian chạy), nhưng không bao giờ được dùng để `if/else` trong logic nghiệp vụ.

## 3. Tại sao bỏ `CONTROL` zone cũ?
Trong v1, chúng ta có `CONTROL`. Nhưng thực tế nó chồng chéo với Global Config và Signal.
Trong v2:
- Cấu hình tĩnh -> **Global Context**.
- Tín hiệu động -> **Signal Zone**.
Mọi thứ trở nên rõ ràng và trực giao (Orthogonal) hơn.

---
**Thực hành:**
Review lại code của bạn. Có biến nào đang đặt tên sai Zone không? Ví dụ `ctx.domain.is_finished` (đang là Data) nên đổi thành `ctx.domain.sig_finished` (Signal) không?