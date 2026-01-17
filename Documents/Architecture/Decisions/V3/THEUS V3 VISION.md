## Câu hỏi: Kể cả khi quyết định giải quyết tất cả ở v3, làm thế nào Theus vẫn giữ được triết lý minh bạch và thiết kế xoay quanh context 3 trục, workflow, và process vốn có của nó mà ko bị biến thành 1 mớ hỗ độn khó giải thích, khó bảo trì.?

Đây là câu hỏi quan trọng nhất để quyết định sự sống còn của **Triết lý POP**. Nếu v3.0 biến Theus thành một "quái vật kỹ thuật" mà người thường không thể hiểu, thì dù hiệu năng có tăng gấp 100 lần, dự án cũng thất bại về mặt tôn chỉ.

Để giải quyết mâu thuẫn giữa **Sức mạnh Kỹ thuật (Rust/Async)** và **Sự Minh bạch (POP Philosophy)**, bạn cần áp dụng chiến lược **"Tảng Băng Trôi" (The Iceberg Strategy)**: Đẩy toàn bộ sự phức tạp xuống tầng chìm (Engine/Rust), giữ cho tầng nổi (Developer API/Python) phẳng lặng và đơn giản.

Dưới đây là 4 nguyên tắc thiết kế để Theus v3 vẫn là Theus, nhưng mạnh mẽ hơn:

### 1. Nguyên tắc "Đa hình, Đơn tướng" (Polymorphic Execution, Monomorphic Interface)

Vấn đề lớn nhất là sự pha trộn giữa Sync và Async (Async Coloring). Nếu bắt người dùng phải lo lắng về `await`, `loop`, `threadpool`, mã nguồn sẽ trở nên hỗn độn.

**Giải pháp:** Theus v3 phải "nói dối" người dùng một cách khéo léo.

* **Giao diện (User sees):** Vẫn là `@process`. Người dùng viết hàm `def` (nếu tính toán) hoặc `async def` (nếu gọi IO). Họ không cần quan tâm Engine chạy nó thế nào.
* **Thực thi (Engine does):** Engine (Rust) tự động kiểm tra chữ ký hàm (Function Signature).
* Nếu là `async def`: Đẩy vào `Tokio Runtime`.
* Nếu là `def`: Đẩy vào `Rayon ThreadPool`.


* **Kết quả:** Quy trình (Process) vẫn là một khối logic nguyên tử. Workflow YAML không đổi.

### 2. Context 3 Trục: Từ "Từ điển mở" sang "Két sắt thông minh"

Ở v2, Context 3 trục được thi hành bằng kỷ luật (Convention). Ở v3, khi có Async và Parallel, kỷ luật là không đủ.

**Giải pháp:** Biến Context thành một cấu trúc dữ liệu Rust (Struct) được bọc kín (Encapsulated).

* **Zero-Copy Immutability:** Người dùng không còn *sửa* Context, họ *yêu cầu* bản cập nhật.
* Thay vì: `ctx.domain.x = 1` (Dễ gây Race Condition).
* Hãy dùng: `ctx.domain.update(x=1)` (Atomic).


* **Tại sao vẫn minh bạch?** Vì hành động `update` là tường minh. Nó giữ nguyên triết lý "Mô tả công việc" của POP. Dữ liệu vẫn được phân chia rõ ràng vào Data/Signal/Meta, nhưng giờ đây nó được "đóng băng" để an toàn giữa các luồng.

### 3. Workflow: Giữ nguyên tính "Declarative" (Khai báo)

Đừng mang sự phức tạp của Async (Await, Future, Promise) vào file cấu hình Workflow. Workflow là bản đồ chiến lược, không phải mã lệnh kỹ thuật.

**Giải pháp:** Workflow FSM quản lý trạng thái chờ đợi thay cho code.

* Nếu một Process là Async (ví dụ: Gọi AI và chờ 10s), Engine sẽ chuyển trạng thái FSM sang `WAITING_IO`.
* Khi có kết quả (từ Outbox hoặc Callback), FSM chuyển sang `PROCESSING`.
* **Minh bạch:** Người đọc Workflow chỉ thấy: Bước A -> Bước B. Họ không cần biết ở giữa đó là một sự chờ đợi phức tạp của Async IO.

### 4. Transactional Outbox: Sự trung thực tuyệt đối

Thay vì làm cho code rối rắm với các logic "Try-Catch-Retry" để ghi DB, v3 sẽ làm cho Process trở nên **thuần khiết hơn**.

**Giải pháp:**

* Process v3 chỉ làm một việc duy nhất: **Ra quyết định**.
* *Code:* `ctx.outbox.add(SendEmail(...))`


* Việc thực thi (Gửi mail thật, Retry khi lỗi mạng, chờ Async) là việc của **Engine Worker**.
* **Tác động:** Code của Process trở nên ngắn gọn, dễ đọc, dễ test hơn bao giờ hết vì bỏ đi được toàn bộ code xử lý lỗi IO (Side-effect management). Đây chính là đỉnh cao của sự minh bạch.

---

### Ví dụ Thực tế: Before & After (Góc nhìn Developer)

Hãy xem sự thay đổi từ v2 lên v3. Bạn sẽ thấy mã nguồn người dùng **gần như không thay đổi**, hoặc thậm chí sạch hơn.

**Mục tiêu:** Lấy dữ liệu user, gọi AI phân tích (lâu), lưu DB.

#### Theus v2 (Hiện tại - Sync, Blocking)

```python
@process(inputs=["user_id"], outputs=["analysis"], side_effect=True)
def analyze_user(ctx):
    # Vấn đề: Block toàn bộ hệ thống 5s chờ AI
    result = call_openai(ctx.domain.user_id) 
    # Vấn đề: Nếu dòng dưới lỗi, dòng trên đã tốn tiền vô ích
    db.save(result) 
    ctx.domain.analysis = result

```

#### Theus v3 (Tương lai - Async, Non-blocking, Safe)

```python
# Chỉ cần thêm 'async'. Theus tự lo phần còn lại.
@process(inputs=["user_id"], outputs=["analysis"]) 
async def analyze_user(ctx):
    # Engine chạy cái này trên Tokio, luồng chính vẫn nhận request khác
    result = await call_openai(ctx.domain.user_id)
    
    # Engine chưa ghi DB ngay. Nó lưu vào Outbox. 
    # Nếu crash ngay sau dòng này, DB vẫn sạch.
    ctx.outbox.add(DbWrite(result)) 
    
    # Cập nhật state bằng cơ chế bất biến (Immutable update)
    return ctx.domain.set("analysis", result)

```

### Kết luận

Để Theus v3 không trở thành một mớ hỗn độn:

1. **Đừng bắt người dùng làm kỹ sư hệ thống.** Đừng bắt họ quản lý Thread hay Event Loop.
2. **Giữ API "ngây thơ".** `@process` phải luôn đơn giản.
3. **Dùng sự phức tạp để bảo vệ sự đơn giản.** Rust Core phức tạp để Python API được an toàn.

Nếu làm được điều này, Theus v3 sẽ không phản bội POP Manifesto. Trái lại, nó sẽ là sự hiện thực hóa hoàn hảo nhất của câu nói trong Manifesto: *"Transparency is Safety"* (Minh bạch là An toàn) – bởi vì giờ đây, sự an toàn được bảo đảm bởi Toán học (Rust Type System) chứ không chỉ là Lời hứa (Convention).