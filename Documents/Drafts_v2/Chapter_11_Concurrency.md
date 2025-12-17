# Chương 11: Mô hình Đồng thời và Hiệu năng (Concurrency & Performance)

---

## 11.1. Mục tiêu: Giải quyết "Hai Tử Huyệt" của Concurrency

Mô hình xử lý đồng thời (Concurrency) của POP được thiết kế để giải quyết hai vấn đề sống còn mà mọi kiến trúc hướng quy trình đều gặp phải:
1.  **An toàn Đồng thời (Concurrency Safety):** Làm sao để tránh Race Condition (ghi đè hỗn loạn) và Deadlock?
2.  **Hiệu năng (Performance):** Làm sao để tận dụng đa lõi mà không bị nghẽn cổ chai bởi Lock?

**Ba nguyên tắc bất biến của POP:**
> 1.  **Safety > Clarity > Performance:** An toàn là số 1. Nhanh mà sai thì vô nghĩa.
> 2.  **Explicit Process:** Logic đồng thời phải tường minh, không giấu giếm.
> 3.  **Engine Responsibility:** Gánh nặng bảo vệ Context thuộc về Engine, không phải Developer.

---

## 11.2. Triết lý Phi-Nhị-Nguyên: Phổ Concurrency 3 Cấp

POP không áp đặt "một liều thuốc cho mọi bệnh". Tuỳ vào ngôn ngữ (Python vs Rust) và quy mô (Script vs Cluster), chúng ta có **3 Cấp độ Đồng thời (Three-Level Spectrum)**.

### **Cấp 1: Mượn Tài nguyên (Borrowing Model)**
*(Phù hợp: Rust, C++, Hệ thống Real-time)*

**Cơ chế:**
1.  Process khai báo trước nó cần đọc (Read Set) và ghi (Write Set) những phần nào của Context.
2.  Engine kiểm tra xung đột:
    *   Cho phép nhiều Process **Đọc chung** một vùng.
    *   Chỉ cho phép duy nhất 1 Process **Ghi độc quyền** vào một vùng tại một thời điểm.
3.  Nếu có xung đột Ghi, Process đến sau phải chờ.

**Ưu điểm:**
*   An toàn tuyệt đối (nhờ trình biên dịch hoặc Engine check).
*   Hiệu năng cực cao (Zero-cost abstraction).

**Hạn chế & Câu hỏi cần giải quyết:**
*   *Deadlock:* Xử lý sao nếu P1 giữ A chờ B, P2 giữ B chờ A?
*   *Starvation:* Process quan trọng có bị process nhỏ chặn đường không?

**Giả định nền tảng:**
*   Process phải khai báo Contract chính xác 100%.

---

### **Cấp 2: Gộp Sai biệt (Delta Aggregation Model)**
*(Phù hợp: Python, JavaScript, AI Glue Code)*

**Cơ chế:**
1.  **Snapshot:** Mỗi Process chạy trên một bản sao (hoặc view) riêng biệt. Không ai nhìn thấy ai.
2.  **No Lock:** Các Process chạy song song hoàn toàn, không cần chờ đợi.
3.  **Delta:** Khi chạy xong, Process trả về một danh sách các thay đổi (Delta).
4.  **Merge:** Engine thu thập tất cả Delta và hợp nhất vào Context gốc một lần duy nhất.

**Ưu điểm:**
*   Không bao giờ có Deadlock.
*   Cực kỳ dễ debug (vì logic tuyến tính).
*   Tốt cho ngôn ngữ có GIL như Python (dùng Multiprocessing).

**Hạn chế & Câu hỏi quan trọng:**
*   *Merge Conflict:* Nếu P1 sửa `x=1`, P2 sửa `x=2`, ai thắng? (Cần Merge Policy).
*   *Memory Bloat:* Nếu Delta quá lớn (ví dụ ảnh 4K), RAM có chịu nổi không?

**Giả định nền tảng:**
*   Tỷ lệ xung đột thấp.
*   Dữ liệu Delta có kích thước chấp nhận được.

---

### **Cấp 3: Phân mảnh (Sharding / Actor Model)**
*(Phù hợp: Hệ thống phân tán, Cluster lớn)*

**Cơ chế:**
Thay vì một Context khổng lồ, ta chia dữ liệu thành các **Shard** (Mảnh) độc lập. Mỗi Shard do một "Actor" quản lý. Các Process giao tiếp bằng cách gửi tin nhắn (pass message) giữa các Shard.

**Ưu điểm:**
*   Scale không giới hạn theo chiều ngang (Horizontal Scaling).
*   Không có bộ nhớ chia sẻ (Shared Memory) -> Không có Race Condition.

**Lưu ý:**
POP khuyến khích chiến lược **"Robust Monolith First"**. Hãy tối ưu Cấp 1 & 2 trước khi nghĩ đến Cấp 3. Đừng giết gà bằng dao mổ trâu.

---

## 11.3. Chiến lược Tối ưu Hiệu năng

Làm sao để tạo Snapshot liên tục mà không chậm máy? POP sử dụng 2 kỹ thuật:

### **1. Copy-on-Write (Sao chép khi Ghi)**
*   Khi Process đọc: Dùng chung pointer với dữ liệu gốc (Chi phí = 0).
*   Chỉ khi Process **Ghi**: Engine mới copy vùng dữ liệu đó sang chỗ mới.
*   *Thách thức:* Cần kiểm soát kỹ Reference Count để tránh Memory Leak.

### **2. Persistent Data Structures (Cấu trúc Bền vững)**
*   Sử dụng các cấu trúc dữ liệu dạng cây (Tree) chia sẻ cấu trúc (Structural Sharing).
*   Tạo ra phiên bản mới của một Dictionary 1 triệu phần tử chỉ tốn O(1) hoặc O(log N) thay vì O(N).
*   *Thách thức:* Không phải ngôn ngữ nào cũng hỗ trợ tốt (Clojure/Scala rất mạnh, Python cần thư viện `pyrsistent` hoặc `immutables`).

---

## 11.4. Yêu cầu Thu thập Dữ liệu (Metrics)

"Không đo lường thì đừng tối ưu". Để chọn mô hình đúng, bạn cần thu thập:
1.  **Tần suất Đọc/Ghi:** Shard nào là "điểm nóng" (Hot Shard)?
2.  **Kích thước Delta:** Trung bình bao nhiêu KB/MB?
3.  **Tỷ lệ Sung đột (Conflict Rate):** Bao nhiêu % process tranh nhau ghi cùng 1 biến?
4.  **Độ trễ I/O:** Hệ thống có bị block bởi Database/Network không?

Nếu không có số liệu này, việc chọn Cấp 1 hay Cấp 2 chỉ là đoán mò.

---

## 11.5. Bảy (7) Giả định Cốt lõi

Sự thành công của mô hình Concurrency POP dựa trên 7 trụ cột niềm tin:
1.  **Contract Đúng:** Process không được nói dối về Input/Output.
2.  **Shard Hợp lý:** Không để 1 Shard gánh 99% tải.
3.  **Merge Rõ ràng:** Xử lý xung đột phải có quy tắc (Last-write wins hoặc Custom merge).
4.  **Chấp nhận Reject:** Hệ thống được quyền từ chối Process nếu quá tải.
5.  **Năng lực Engine:** Team dev có đủ trình độ để implement Engine (hoặc dùng SDK chuẩn).
6.  **Delta Vừa phải:** Không dùng Delta để truyền tải Video 8K Uncompressed (hãy dùng pointer/reference).
7.  **Không Độc quyền:** Shard không được trở thành cổ chai duy nhất.

> **Cảnh báo:** Nếu một trong các giả định này sai, mô hình Concurrency sẽ sụp đổ.
