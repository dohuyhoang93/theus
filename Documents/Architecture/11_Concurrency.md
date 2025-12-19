# Chương 11: Mô hình Đồng thời (Concurrency)

---

## 11.1. Quan điểm về Đa luồng: "Less is More"

Concurrency (Đồng thời) là con dao hai lưỡi.
*   Dùng đúng: Hiệu năng x10.
*   Dùng sai: Debug x100 (thời gian).

Theus chọn cách tiếp cận cực đoan: **Single Threaded by Default**.
Tại sao? Vì **An toàn là số 1**. Một hệ thống Robot đâm vào tường vì Race Condition là không thể chấp nhận được.

---

## 11.2. Mô hình "Nhiều Nhánh, Một Gốc" (Many Branches, One Trunk)

Mặc dù mặc định là đơn luồng, Theus vẫn hỗ trợ Concurrency thông qua 3 cơ chế an toàn:

### Level 1: I/O Concurrency (Async/Thread)
Dành cho việc chờ đợi (Network, Disk).
*   **Cách dùng:** Sử dụng `ThreadPoolExecutor` BÊN TRONG một Process.
*   **Quy tắc:** Process phải tự quản lý thread của mình và `join` tất cả trước khi return. Context KHÔNG được chia sẻ cho thread con (hoặc chỉ đọc).

### Level 2: Pipeline Parallelism (Local Immutability)
Dành cho xử lý dữ liệu nặng (Image Processing).
*   **Cách dùng:** Chạy nhiều worker process song song. Mỗi worker nhận một bản **Deep Copy** của Context.
*   **Cơ chế:**
    1.  Master clone context -> `ctx_1`, `ctx_2`.
    2.  Worker 1 chạy trên `ctx_1`, Worker 2 chạy trên `ctx_2`.
    3.  Master nhận kết quả và merge lại.
*   **Ưu điểm:** Không bao giờ có Race Condition vì không ai dùng chung bộ nhớ.

### Level 3: Distributed Nodes (Sharding)
Dành cho hệ thống khổng lồ.
*   **Cách dùng:** Chạy nhiều Theus Node trên nhiều máy. Giao tiếp qua Queue (Redis/RabbitMQ).
*   **Ưu điểm:** Scale vô tận.

---

## 11.3. Hiệu năng & Tối ưu

Nếu chạy Single Thread thì có chậm không?
*   **Với I/O Bound (Web, Database):** Không chậm, vì thời gian chủ yếu là chờ đợi.
*   **Với CPU Bound (AI, Image):** Có thể chậm.
    *   *Giải pháp:* Đẩy tác vụ nặng xuống tầng C++/Rust (thông qua thư viện như NumPy, OpenCV). Python chỉ làm nhiệm vụ "gọi hàm".

> **Lời khuyên:** Đừng vội vàng tối ưu (Premature Optimization). Hãy viết code đơn luồng cho chạy đúng trước. Khi nào profiler báo chậm thì hãy bật Parallel.

---

## 11.4. Kết luận
Trong Theus:
*   Mặc định: An toàn (Serial).
*   Khi cần: Tốc độ (Parallel via Isolation).

Chúng tôi thà để máy chạy chậm hơn 10ms còn hơn để kỹ sư mất 10 đêm debug lỗi Race Condition.
