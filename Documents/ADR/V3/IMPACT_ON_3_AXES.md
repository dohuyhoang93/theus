# Phân tích Tác động v3.0: Sự Cường hóa Mô hình Context 3 Trục
**Ngày:** 2026-01-15
**Phiên bản:** Theus v3.0 Vision
**Triết lý:** Chuyển dịch từ "Quy ước" (Convention) sang "Ràng buộc Vật lý" (Physical Constraints).

---

# 1. Trục Dữ liệu (Zone Axis): Sự phân hóa "Âm - Dương"
*Mục đích: Tối ưu hóa cấu trúc lưu trữ dựa trên bản chất dữ liệu.*

Trong v2, các Zone (Data, Signal, Meta) nằm chung trong một dictionary phẳng, dựa vào prefix tên để phân biệt.

* **Tác động của v3:** **Hybrid Schema** xé lẻ cấu trúc lưu trữ để trả lại đúng vị trí cho từng loại dữ liệu:
* **Data Zone (Dương - Trật tự):** Lưu trong **Domain Context** (Immutable Struct). Đây là nơi lưu "Sự thật" (Truth), hỗ trợ Audit log đầy đủ và truy cập O(1).
* **Signal/Meta Zone (Âm - Linh hoạt):** Đẩy sang **Event Bus (Tokio Channel)** hoặc **Scratchpad**. Nơi này chấp nhận tính động (Dynamic), phù hợp cho sự kiện Real-time và Log hệ thống.
* **Heavy Zone (Hỗn mang - Thực dụng):** (Mới) Vùng dành cho AI Model/Tensor lớn. Dùng **Reference Counting (Arc)** để tồn tại an toàn mà không bị sao chép.

> **Tổng kết:** Zone Axis không còn là sự sắp xếp trong cùng một cái túi, mà là sự phân chia lãnh thổ vật lý rõ rệt.

---

# 2. Trục Phạm vi (Layer Axis): Từ "Ý thức" sang "Tự động hóa"
*Mục đích: Quản lý vòng đời (Lifecycle) và rác bộ nhớ.*

Trong v2, việc dọn dẹp biến `Local` hay bảo vệ `Global` dựa hoàn toàn vào ý thức lập trình viên.

* **Tác động của v3:** Cơ chế **"Lifecycle Enforcers"** biến trục này thành quy luật sinh tồn bất biến.
* **Local:** Gắn liền với Stack Frame của Async Task. Engine tự động **Hủy (Drop)** toàn bộ dữ liệu Local ngay khi Process kết thúc. Không còn rác bộ nhớ.
* **Global:** Được bảo vệ bởi **Zero-Copy Immutability**. Mọi nỗ lực ghi trực tiếp vào Global sẽ bị chặn đứng (Compile Error/Runtime Guard). Sự thay đổi chỉ xảy ra qua commit Transaction.

> **Tổng kết:** Layer Axis chuyển từ khái niệm không gian ("nằm ở đâu") sang khái niệm thời gian ("sống bao lâu").

---

# 3. Trục Ngữ nghĩa (Semantic Axis): Từ "Nhãn dán" sang "Luật sắt"
*Mục đích: Định nghĩa Hành vi và Quyền hạn.*

Trước đây, nhãn `Input`, `Output`, `SideEffect` chỉ mang tính khai báo. Một process khai báo `Input` vẫn có thể lén sửa data.

* **Tác động của v3:**
* **Input (Read-only):** Với **Immutable Struct**, `Input` trở thành tham chiếu bất biến thực sự. Bạn không thể sửa nó ngay cả khi muốn. Thêm vào đó là **Input Firewall**: Pure Process bị cấm nhìn thấy Signal/Meta.
* **Output (Write):** **Hierarchical Scopes** cho phép định nghĩa chính xác `outputs=["domain.user.*"]`. Engine chặn mọi nỗ lực ghi ra ngoài phạm vi này.
* **SideEffect (Intent):** Pattern **Transactional Outbox** tách biệt hoàn toàn việc tính toán và thực thi IO. Semantic "SideEffect" giờ đây là việc đẩy một message vào `Outbox`. Không còn code `send_email()` nằm lẫn lộn trong logic nghiệp vụ.

> **Tổng kết:** Semantic Axis trở thành người gác cổng (Bouncer) thực sự, không còn là tấm bảng chỉ dẫn.

---

# 🧬 Tổng kết: Sự chuyển dịch Triết lý

Việc nâng cấp lên v3 sẽ thay đổi bản chất của Context 3 Trục như sau:

| Đặc tính | Theus v2 (Hiện tại) | Theus v3 (Tương lai) |
| :--- | :--- | :--- |
| **Bản chất** | Là một kho chứa dữ liệu thụ động. | Là một hệ thống bảo vệ chủ động. |
| **Cơ chế** | Dựa trên niềm tin (Trust-based). | Dựa trên bằng chứng (Proof-based via Rust/Types). |
| **Sự minh bạch** | Minh bạch nhờ quy ước đặt tên. | Minh bạch nhờ cấu trúc luồng dữ liệu (Data Flow). |
| **Kiến trúc** | Phẳng (Flat Dict). | Đa chiều vật lý (Struct, Channel, Arc, Log). |

**Kết luận chung:** Theus v3 không làm mất đi triết lý Context 3 trục. Nó biến triết lý đó từ **"Lời hứa của Developer" (Convention)** thành **"Sự đảm bảo của Toán học" (Physical Constraint)**. Bạn vẫn tư duy theo 3 trục, nhưng giờ đây hệ thống sẽ ngăn bạn vi phạm các nguyên tắc của chính trục đó.
