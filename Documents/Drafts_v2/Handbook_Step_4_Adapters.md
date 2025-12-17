# Bước 4: Tương tác với Thực tại (Interacting with Reality)

---

## 4.1. Chuyện nhà Dev: "Con tin của Công nghệ"

Bạn viết logic xét duyệt vay vốn.
*   Hôm nay: Sếp bảo lấy điểm tín dụng từ CIC (API).
*   Ngày mai: Sếp bảo lấy từ Database nội bộ.
*   Ngày kia: Sếp bảo lấy từ file Excel do đối tác gửi.

Nếu bạn viết `requests.get("https://cic.vn/...")` ngay trong hàm xử lý, logic của bạn đã chết dính với CIC. Khi sếp đổi ý, bạn phải đục code ra sửa. Logic nghiệp vụ trở thành **"Con tin"** của công nghệ.

Vấn đề:
1.  **Khó thay đổi:** Đổi DB = Sửa Logic.
2.  **Khó Test:** Muốn test hàm xét duyệt lại phải có mạng internet để gọi API thật.
3.  **Lộn xộn:** Code nghiệp vụ (vay vốn) lẫn lộn với code kỹ thuật (JSON, HTTP, SQL).

---

## 4.2. Giải pháp POP: Adapter (Người phiên dịch)

POP áp dụng triệt để quy tắc: **Logic Nghiệp vụ không được biết về Công nghệ bên ngoài.**
Nó chỉ ra lệnh: *"Lấy cho tôi điểm tín dụng"*.
Ai lấy? Lấy ở đâu? Bằng cách nào? -> Đó là việc của **Adapter**.

*   **Process:** Lõi trong sạch (Pure).
*   **Adapter:** Lớp vỏ bọc (Dirty). Đây là nơi chứa code SQL, HTTP request, File IO.
*   **Context:** Nơi Process gặp gỡ Adapter.

---

## 4.3. Thực hành: Gửi Email mà không cần biết SMTP

Hãy xây dựng tính năng gửi email.

### **Bước A: Viết Adapter**
Tạo file `src/adapters/email_adapter.py`. Adapter chỉ là một class bình thường, không cần decorator gì cả.

```python
# src/adapters/email_adapter.py
class EmailAdapter:
    def send(self, to_addr: str, title: str, content: str):
        # Code kỹ thuật nằm ở đây (SMTP, SendGrid, Mailgun...)
        print(f"[Real Email Sent] To: {to_addr} | Title: {title}")
        # Trong thực tế: smtp.sendmail(...)
```

### **Bước B: Mở rộng Context (QUAN TRỌNG)**
Mặc định `pop-sdk` chỉ cho bạn Global và Domain. Bạn cần thêm một ngăn chứa Adapter. 
**Lưu ý Kỹ thuật:** Bạn PHẢI đặt tên biến có đuôi `_ctx` (ví dụ `env_ctx`) để kích hoạt cơ chế bảo vệ đệ quy (Recursive Guard) của SDK.

Mở `src/context.py`:

```python
from dataclasses import dataclass
from pop import BaseSystemContext, BaseGlobalContext, BaseDomainContext
# Import Adapter
from src.adapters.email_adapter import EmailAdapter

# ... (Global & Domain giữ nguyên) ...

@dataclass
class EnvContext:
    email_client: EmailAdapter = None  # Nơi chứa Adapter

@dataclass
class SystemContext(BaseSystemContext):
    global_ctx: GlobalContext
    domain_ctx: DomainContext
    
    # Kỷ luật POP: Phải có suffix _ctx
    env_ctx: EnvContext = None 
```

### **Bước C: Đăng ký trong `main.py`**
Chúng ta phải nhét Adapter thật vào Context lúc khởi chạy.

```python
# main.py
ctx = SystemContext(
    global_ctx=GlobalContext(),
    domain_ctx=DomainContext(),
    env_ctx=EnvContext(
        email_client=EmailAdapter() # Bơm hàng thật vào đây
    )
)
```

### **Bước D: Sử dụng trong Process**
Giờ thì Process chỉ việc gọi `env.email_client`. Lưu ý `inputs` khai báo là `env...`.

```python
@process(
    name="send_welcome_email",
    inputs=['domain.user', 'env.email_client'], # Xin quyền dùng Email
    outputs=[],
    side_effects=['SEND_EMAIL']
)
def send_welcome_email(ctx: SystemContext):
    user = ctx.domain.user
    
    # SDK Guard tự động map 'env' -> 'env_ctx'
    # Bạn gọi ctx.env_ctx.email_client
    ctx.env_ctx.email_client.send(
        to_addr=user.email,
        title="Welcome!",
        content="Xin chào mừng bạn đến với POP!"
    )
```

> **Góc Chuyên gia: Tại sao phải là `env_ctx`?**
> Nếu bạn đặt tên là `env` (không có `_ctx`), SDK sẽ coi đó là một biến thường (như `int` hay `str`). Khi Process truy cập `ctx.env`, SDK sẽ trả về nguyên cục Object Adapter mà không kiểm soát tiếp các con bên trong. Process có thể lén lút gọi `env.database` dù không xin phép.
> Khi dùng `env_ctx`, SDK hiểu đây là một Lớp (Layer) và sẽ tiếp tục soi xét quyền truy cập bên trong nó.

---

## 4.4. Tại sao làm thế này lại sướng?

Khi bạn muốn chạy Unit Test, bạn không cần cài SMTP Server. Bạn chỉ cần viết một `MockEmailAdapter`:

```python
class MockEmailAdapter:
    def send(self, to_addr, title, content):
        print("Giả vờ gửi email thôi!")

# Trong file test
ctx.env_ctx.email_client = MockEmailAdapter()
# Chạy process -> code chạy vèo vèo, không phụ thuộc mạng.
```

---

## 4.5. Tổng kết Bước 4

*   **Adapter Pattern:** Đẩy hết những thứ "bẩn" (IO, Side-effect) ra rìa hệ thống.
*   **Env Context:** Nơi chứa Adapter. Phải tuân thủ quy tắc đặt tên `_ctx`.
*   **Dependency Injection:** Context là nơi bơm (inject) Adapter vào Process.

**Thử thách:** Hãy viết một `StockAdapter` (để lấy tồn kho) và inject nó vào `env_ctx`. Sau đó sửa process `validate_order` ở Bước 2 để dùng `ctx.env_ctx.stock_adapter.check_availability(sku)` thay vì truy cập `domain.warehouse` trực tiếp.
