# Bước 5: Quản lý Sự phức tạp (The Orchestrator)

---

## 5.1. Khi YAML trở nên quá tải

Dự án lớn dần. Bạn bắt đầu có nhu cầu:
*   "Nếu là VIP thì chạy A, còn không chạy B".
*   "Lặp lại bước X cho đến khi thành công".
*   "Chạy song song 3 model AI để lấy kết quả nhanh nhất".

Nếu bạn cố nhồi nhét logic này vào `workflow.yaml`, nó sẽ trở thành một mớ hỗn độn (Spaghetti YAML).
Theus có quy tắc: **YAML phải phẳng (Flat) và Tĩnh (Static).**

---

## 5.2. Orchestrator Pattern: Giấu sự phức tạp vào code

Thay vì làm YAML phức tạp, hãy tạo một Process đặc biệt gọi là **Orchestrator**.

```python
@process(
    inputs=["domain.user.rank"],
    outputs=["domain.commands.next_action"]
)
def decide_vip_flow(ctx):
    rank = ctx.domain.user.rank
    
    if rank == "VIP":
        # Orchestrator quyết định logic phức tạp ở đây
        if is_weekend():
             ctx.domain.commands.next_action = "GIFT_VOUCHER"
        else:
             ctx.domain.commands.next_action = "FAST_TRACK"
    else:
        ctx.domain.commands.next_action = "NORMAL_QUEUE"
        
    return ctx.done()
```

Trong YAML, bạn chỉ cần 2 dòng:
```yaml
- "domain.behavior.decide_vip_flow"
- "domain.behavior.execute_decision"
```

Sự phức tạp đã được gói gọn vào trong Python - nơi giỏi xử lý logic nhất.

---

## 5.3. Xử lý Song song (Internal Parallelism)

Theus mặc định chạy đơn luồng (Single Thread) để đảm bảo an toàn.
Nhưng nếu bạn cần download 10 file ảnh cùng lúc?

Hãy dùng `ThreadPoolExecutor` **bên trong** Process.

```python
from concurrent.futures import ThreadPoolExecutor

@process(...)
def download_images(ctx):
    urls = ctx.domain.inputs.urls
    
    def _download(url):
        # Code download here
        pass
        
    # Tự quản lý luồng nội bộ
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_download, urls))
        
    ctx.domain.outputs.images = results
    return ctx.done()
```

**Lưu ý:** Context không an toàn để chia sẻ (Not Thread-Safe). Trong hàm `_download`, đừng bao giờ ghi trực tiếp vào `ctx`. Hãy trả kết quả về (return) và để luồng chính (Main Thread) ghi vào Context.

---

## 5.4. Vòng lặp & Retry

Nếu cần lặp lại một hành động (như thử connect lại Database)?
Hãy dùng vòng lặp `while` hoặc thư viện `tenacity` ngay trong Process.

```python
@process(...)
def connect_db_with_retry(ctx):
    attempt = 0
    while attempt < 3:
        try:
            connect()
            return ctx.done()
        except error:
            attempt += 1
            sleep(1)
            
    return ctx.fail("CONNECTION_FAILED")
```

Đừng bắt Engine phải có tính năng "Retry Step". Process nên tự chịu trách nhiệm về độ bền (Resilience) của chính mình.

---

## 5.5. Tổng kết

*   Giữ `workflow.yaml` đơn giản.
*   Đẩy logic rẽ nhánh, vòng lặp phức tạp vào trong **Orchestrator Process**.
*   Sử dụng Parallelism bên trong Process nhưng phải tuân thủ quy tắc "Main Thread Write Only".
