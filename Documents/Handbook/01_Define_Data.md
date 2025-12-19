# Bước 1: Từ Hỗn loạn đến Ngăn nắp (Taming the Data)

---

## 1.1. Chuyện nhà Dev: "Biến Config bị ai sửa?"

Hãy tưởng tượng bạn quay lại dự án sau 2 tháng nghỉ phép. Bạn nhận được ticket: *"App crash khi user đổi theme sang Dark Mode."*
Bạn mở code ra và thấy biến `config` toàn cục bị sửa lung tung bởi 3 ông Dev khác nhau.
Code của bạn đang ở trạng thái **Hỗn loạn (Chaos)**.

---

## 1.2. Giải pháp POP: Ngôi nhà Dữ liệu (Context)

Trong POP, nguyên tắc đấu tiên là: **"Dữ liệu không được vô gia cư."**
Mọi dữ liệu phải thuộc về một ngôi nhà cụ thể gọi là **Context**.

Chúng ta chia "ngôi nhà" này thành 3 phòng:
1.  **System Context:** Root Container.
2.  **Global Context (Phòng Khách):** Chứa cấu hình tĩnh (Config, Constants). Chỉ đọc.
3.  **Domain Context (Phòng Làm việc):** Chứa dữ liệu nghiệp vụ (User Profile, Orders). Thay đổi liên tục.

---

## 1.3. Tư duy Thiết kế: 3 Câu hỏi Vàng (3-Axis Thinking)
Trước khi khai báo một biến vào Context, hãy tự hỏi 3 câu sau:

1.  **Sống bao lâu?** (Layer)
    *   Toàn bộ vòng đời App? -> `Global`
    *   Chỉ 1 Request/Workflow? -> `Domain`
    *   Chỉ trong 1 hàm? -> `Local`
2.  **Là Tài sản hay Tín hiệu?** (Zone)
    *   Cần lưu lại? -> `Data` (Mặc định)
    *   Chỉ để kích hoạt gì đó rồi quên luôn? -> `Signal` (Prefix `sig_`)
    *   Chỉ để debug? -> `Meta` (Prefix `meta_`)
3.  **Dùng để làm gì?** (Semantic)
    *   Đọc? -> `Input`
    *   Ghi? -> `Output`

---

## 1.4. Single Source of Truth: `context_schema.yaml`

Trong Theus, chúng ta không định nghĩa dữ liệu bằng miệng hay bằng comment. Chúng ta dùng **Hợp đồng (Contract)**.

File `specs/context_schema.yaml`:

```yaml
context:
  domain:
    # Định nghĩa cấu trúc dữ liệu nghiệp vụ
    user:
      name: string
      age: integer
      role: enum(admin, user, guest)
    order:
      id: string
      amount: float
      items: list
```

Đây là **Sự thật duy nhất**. Mọi code Python, mọi test case đều phải tuân thủ schema này.

---

## 1.5. Thực hành: Khởi tạo Dự án

Dùng CLI để dựng bộ khung chuẩn:

```bash
theus init my_agent
cd my_agent
```

Cấu trúc thư mục mới:

```text
my_agent/
├── specs/                # <--- CẤU HÌNH CỐT LÕI
│   ├── context_schema.yaml
│   └── audit_recipe.yaml
├── workflows/            # Kịch bản chạy (YAML)
│   └── main_workflow.yaml
└── src/
    ├── context.py        # Implementation của Schema
    └── processes/        # Logic
```

---

## 1.6. Implementation: `context.py`

Dù Schema là YAML, nhưng chúng ta vẫn cần Class Python để có **Autocompletion** trong IDE.
Theus khuyến khích dùng `dataclasses` để map 1-1 với Schema.

```python
# src/context.py
from dataclasses import dataclass, field
from typing import List
from theus import BaseDomainContext, BaseGlobalContext

# 1. Global: Cấu hình Tĩnh
@dataclass
class GlobalContext(BaseGlobalContext):
    app_name: str = "SmartAgent"

# 2. Domain: Mapping với Schema "domain"
@dataclass
class DomainContext(BaseDomainContext):
    user_name: str = ""
    user_age: int = 0
    order_items: List[str] = field(default_factory=list)
```

> **Lưu ý:** Trong tương lai, bước này có thể được tự động hóa (Code Gen).

---

## 1.7. Tổng kết Bước 1

Chúng ta chưa viết logic xử lý nào, nhưng chúng ta đã thắng lớn:
*   **Minh bạch:** Nhìn vào `specs/context_schema.yaml` là hiểu toàn bộ dữ liệu dự án.
*   **An toàn:** Code Python `context.py` đảm bảo Type Safety.
*   **Chuẩn hóa:** Không còn biến toàn cục trôi nổi.

**Thử thách:** Hãy chạy `pop init`, sau đó mở `specs/context_schema.yaml` và thêm field `todo_items: list`. Sau đó cập nhật `src/context.py` tương ứng.
