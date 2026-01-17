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

Mặc dù mặc định là đơn luồng, Theus vẫn hỗ trợ Concurrency thông qua 4 cơ chế an toàn:

### Level 1: I/O Concurrency (Async/Thread)
Dành cho việc chờ đợi (Network, Disk).
*   **Cách dùng:** Sử dụng `async/await` hoặc `ThreadPoolExecutor` BÊN TRONG một Process.
*   **Quy tắc:** Process phải tự quản lý thread của mình và `join` tất cả trước khi return. Context KHÔNG được chia sẻ cho thread con (hoặc chỉ đọc).

### Level 2: Pipeline Parallelism (Local Immutability)
Dành cho xử lý dữ liệu nặng (Image Processing).
*   **Cách dùng:** Chạy nhiều worker process song song. Mỗi worker nhận một bản **Deep Copy** của Context.
*   **Cơ chế:**
    1.  Master clone context -> `ctx_1`, `ctx_2`.
    2.  Worker 1 chạy trên `ctx_1`, Worker 2 chạy trên `ctx_2`.
    3.  Master nhận kết quả và merge lại.
*   **Ưu điểm:** Không bao giờ có Race Condition vì không ai dùng chung bộ nhớ.

### Level 3: Sub-Interpreters (v3.0 - Python 3.14+)
**Tính năng mới trong v3.0.** Dành cho true parallelism trong cùng một process.
*   **Cách dùng:** Mỗi agent chạy trong sub-interpreter riêng với GIL riêng.
*   **Cơ chế:**
    ```
    Main Interpreter (GUI Thread)
        |
        +-- Sub-Interpreter 1 (Agent A) - Own GIL
        |
        +-- Sub-Interpreter 2 (Agent B) - Own GIL
        |
        +-- Rust Context Backend (Shared Memory) - No GIL needed
    ```
*   **Ưu điểm:** True parallelism, shared state qua Rust backend.

### Level 4: Distributed Nodes (Sharding)
Dành cho hệ thống khổng lồ.
*   **Cách dùng:** Chạy nhiều Theus Node trên nhiều máy. Giao tiếp qua Queue (Redis/RabbitMQ).
*   **Ưu điểm:** Scale vô tận.

---

## 11.3. SignalHub (v3.0 - Tokio-Powered)

Theus v3.0 giới thiệu **SignalHub** - event system hiệu năng cao cho multi-agent communication.

```python
from theus_core import SignalHub

# Tạo hub (Tokio broadcast channel backend)
hub = SignalHub(capacity=1000)

# Nhiều receivers (subscribers)
receiver1 = hub.subscribe()
receiver2 = hub.subscribe()

# Gửi event (non-blocking)
hub.send("AGENT_READY", {"agent_id": 1})

# Nhận event (blocking hoặc async)
event = receiver1.recv()
event = await receiver1.recv_async()
```

**Performance:** 2.7+ million events/second.

---

## 11.4. Hiệu năng & Tối ưu

Nếu chạy Single Thread thì có chậm không?
*   **Với I/O Bound (Web, Database):** Không chậm, vì thời gian chủ yếu là chờ đợi. Dùng `async` processes.
*   **Với CPU Bound (AI, Image):** Có thể chậm.
    *   *Giải pháp 1:* Đẩy tác vụ nặng xuống tầng C++/Rust (thông qua NumPy, OpenCV). Python chỉ làm nhiệm vụ "gọi hàm".
    *   *Giải pháp 2:* Dùng Sub-interpreters (Python 3.14+) cho true parallelism.
    *   *Giải pháp 3:* Dùng `strict_mode=False` cho training loops.

> **Lời khuyên:** Đừng vội vàng tối ưu (Premature Optimization). Hãy viết code đơn luồng cho chạy đúng trước. Khi nào profiler báo chậm thì hãy bật Parallel.

---

## 11.5. Kết luận
Trong Theus v3.0:
*   Mặc định: An toàn (Serial).
*   Khi cần: Tốc độ (Parallel via Isolation hoặc Sub-interpreters).

Chúng tôi thà để máy chạy chậm hơn 10ms còn hơn để kỹ sư mất 10 đêm debug lỗi Race Condition.
