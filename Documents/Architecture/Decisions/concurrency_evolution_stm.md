# ADR: Tiến hóa Mô hình Đồng thời - Từ Khóa (Locking) đến Phổ STM

**Trạng thái:** Dự thảo / Tầm nhìn v2.2
**Ngày:** 22/12/2025
**Tác giả:** Theus AI & User

## 1. Bối cảnh & Hiện trạng (Theus v2.1)

### 1.1 Kiến trúc Hiện tại
Theus v2.1 đang sử dụng mô hình **"An toàn Tuyến tính - Ghi trực tiếp"** (Linear Safe - Direct Write):
*   **Thực thi:** Tuần tự theo chuỗi (Process A -> Process B -> Process C).
*   **Truy cập Bộ nhớ:** Ghi đè trực tiếp lên RAM của Context gốc ngay khi lệnh `ctx.x = 1` được gọi.
*   **An toàn:** Dựa hoàn toàn vào **Khóa Bi quan (Pessimistic Locking)** thông qua `LockManager`. Nếu Process A đang chạy (giữ khóa Write), Process B buộc phải đứng chờ.
*   **Rollback:** Sử dụng cơ chế "Nhật ký Hoàn tác" (`Undo Log / _delta_log`). Khi có lỗi, hệ thống đọc ngược log để khôi phục giá trị cũ.

### 1.2 Quy tắc "Cấm Input Điều khiển"
Để ép buộc tư duy **Hướng Trạng thái (State-Driven)**, Theus hiện tại cấm tuyệt đối việc khai báo `SIG_` (Tín hiệu), `CMD_` (Lệnh), hoặc `META_` (Meta) trong danh sách `inputs` của Process.
*   **Lý do:** Process chỉ nên là "Thợ gia công", hoạt động dựa trên nguyên liệu là Dữ liệu bền vững (`DATA Zone`). Các tín hiệu điều khiển (`SIG/CMD`) là việc của "Quản đốc" (Orchestrator/Workflow), không nên lọt vào logic tính toán của Process. Điều này giúp đảm bảo tính Tái lập (Replayability) và Tách biệt trách nhiệm (Separation of Concerns).

## 2. Vấn đề Đặt ra
Mô hình v2.1 tuy an toàn nhưng gặp các giới hạn lớn khi mở rộng quy mô:
1.  **Không thể chạy Song song (No True Parallelism):** Do cơ chế ghi thẳng vào RAM và khóa toàn cục, hai Process không thể chạy đồng thời an toàn dù phần cứng có nhiều lõi CPU.
2.  **Đọc bị Chặn (Blocked Reads):** Quy tắc Zone nghiêm ngặt đôi khi gây khó khăn cho các kịch bản lai ghép (Hybrid) cần đọc nhanh trạng thái lệnh.
3.  **Hiệu năng thấp ở tải cao:** Cơ chế chờ khóa (Stop-and-Wait) làm lãng phí tài nguyên khi có tranh chấp (Lock Contention).

## 3. Phân tích Chi tiết: Hai trường phái Đối lập

Chúng ta đã xem xét hai hướng tiếp cận để giải quyết vấn đề Song song trong v2.2:

### Phương án A: Khóa Bi quan (Truyền thống)
*   **Cơ chế:** Dùng chung bộ nhớ (Shared Memory). Process phải xin khóa cụ thể (ví dụ khóa `domain.user`) trước khi chạy.
*   **Ưu điểm:** Tiết kiệm RAM tối đa, dữ liệu nhất quán tức thì (Real-time).
*   **Nhược điểm:**
    *   **Deadlock (Tử huyệt):** Rủi ro treo hệ thống khi A chờ B và B chờ A.
    *   **Nghẽn cổ chai:** Hiệu năng giảm mạnh khi số lượng process tăng lên.

### Phương án B: Bộ nhớ Giao dịch (STM) / Shadow Fork-Join
*   **Cơ chế:** Mỗi Process được cấp một **Bản sao Bóng (Shadow Copy/Snapshot)** của Context.
    *   **Fork:** Tách nhánh dữ liệu riêng.
    *   **Exec:** Chạy độc lập, ghi vào bộ đệm riêng (Buffered Write).
    *   **Join:** Cuối cùng mới gộp (Merge) lại Context gốc.
*   **Ưu điểm:**
    *   **Zero Deadlock:** Không ai phải chờ ai.
    *   **Isolation:** Process A crash không ảnh hưởng B hay Context gốc.
    *   **Audit "Miễn phí":** Mọi thay đổi nằm trong buffer, dễ dàng kiểm tra trước khi commit.
*   **Nhược điểm:** Tốn RAM (do clone dữ liệu), Cần giải quyết xung đột khi Merge, Có độ trễ nhất định (Latency).

## 4. Giải pháp "Phi Nhị Nguyên": Thanh trượt Cô lập (The Isolation Slider)

Thay vì chọn phe (A hay B), Theus v2.2 đề xuất mô hình **"Phổ Nhất quán" (Consistency Spectrum)**, cho phép Lập trình viên tự quyết định cấu hình mức độ cô lập (Isolation Level) cho từng bước trong Workflow (`workflow.yaml`).

Chúng ta định nghĩa 3 Nấc (Modes):

### Nấc 1: Chế độ An toàn (Safe Mode - STM Thuần thúy)
*   **Hành vi:** Copy toàn bộ (Snapshot). Chạy hoàn toàn độc lập.
*   **Sử dụng khi:**
    *   Giao dịch tài chính (cần Rollback sạch sẽ 100%).
    *   Các tính toán phức tạp chạy song song (Parallel Compute).
    *   Process không được phép gây side-effect lên hệ thống đang chạy nếu lỗi.
*   **Đánh đổi:** Tốc độ chậm nhất, Tốn RAM nhất -> Đổi lấy sự An toàn tuyệt đối.

### Nấc 2: Chế độ Tốc độ (Raw Mode - Direct Access)
*   **Hành vi:** Ghi thẳng vào RAM không qua Buffer (Zero-Copy). Sử dụng khóa lạc quan (Optimistic) hoặc thậm chí không khóa.
*   **Sử dụng khi:**
    *   Cập nhật UI/Dashboard (cần hiện ngay tức thì).
    *   Logging/Tracing tần suất cao.
    *   Hệ thống Game Loop hoặc xử lý tín hiệu media (chấp nhận sai lệch nhỏ).
*   **Đánh đổi:** Tốc độ nhanh nhất -> Đổi lấy rủi ro Race Condition cao.

### Nấc 3: Chế độ Lai (Hybrid Mode - Theus Default)
*   **Hành vi:** Kết hợp ưu điểm.
    *   **Đọc (Read):** Đọc thẳng từ RAM chung (Shared Read) -> Nhanh.
    *   **Ghi (Write):** Ghi vào Buffer cục bộ (Buffered Write).
    *   **Commit:** Khi Process xong, Engine khóa cực nhanh (Micro-lock) để xả Buffer vào RAM.
*   **Sử dụng khi:** 80% logic nghiệp vụ thông thường.
*   **Đánh đổi:** Cân bằng hoàn hảo giữa Tốc độ và An toàn.

## 5. Lộ trình Thực hiện (Roadmap)

1.  **Giai đoạn 1 (Hiện tại - v2.1):**
    *   Giữ nguyên mô hình Linear Safe (tương đương Hybrid nhưng chạy tuần tự).

2.  **Giai đoạn 2 (v2.2 - Nền móng):**
    *   Triển khai `ShadowContext` và `BufferManager` thực sự.
    *   Nâng cấp Transaction từ "Undo Log" sang "Buffered Change Set".

3.  **Giai đoạn 3 (v2.3 - Công bố):**
    *   Hỗ trợ cú pháp YAML: `isolation: safe | raw | hybrid`.
    *   Hỗ trợ chạy song song trong Workflow: `steps: [[ProcA, ProcB]]`.

## 6. Kết luận
Giải pháp "Thanh trượt" này phản ánh đúng triết lý của Theus: Cung cấp công cụ mạnh mẽ nhưng linh hoạt, trao quyền kiểm soát (Control) lại cho Developer thay vì ép buộc một mô hình cứng nhắc.
