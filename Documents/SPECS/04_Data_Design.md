# Chương 4: Thiết kế Dữ liệu (Context Design)

---

## 4.1. Tư duy 3 Trục (The 3-Axis Mindset)

Trong các thiết kế cũ, Context thường chỉ được chia theo "Phạm vi" (Layer). Tuy nhiên, để đáp ứng tiêu chuẩn an toàn công nghiệp, Context của Theus được cấu thành từ **3 Trục Tương giao (Three Intersecting Axes)**. Sự an toàn của hệ thống nằm chính tại giao điểm của ba trục này.

```
                                     [Y] SEMANTIC
                             (Input, Output, SideEffect, Error)
                                      ^
                                      |
                                      |                +------+------+
                                      |               /|             /|
                                      +--------------+ |  CONTEXT   + |----------> [Z] ZONE
                                     /               | |  OBJECT    | |      (Data, Signal, Meta, Heavy)
                                    /                | +------------+ |
                                   /                 |/             |/
                                  /                  +------+------+
                                 v
                            [X] LAYER
                     (Global, Domain, Local)
```

### Trục 1: Phạm vi (Layer) - "Dữ liệu sống ở đâu?"
*   **Global:** Sống toàn cục, bất biến (Config).
*   **Domain:** Sống theo Request/Session (Business State).
*   **Local:** Sống trong 1 Process (Temporary var).

### Trục 2: Ý nghĩa (Semantic) - "Dữ liệu dùng để làm gì?"
Quản lý hợp đồng giao tiếp (Contract).
*   **Input:** Chỉ đọc.
*   **Output:** Chỉ ghi.
*   **Side-Effect:** Ghi ra ngoài.
*   **Error:** Tín hiệu lỗi.

### Trục 3: Vùng (Zone) - "Dữ liệu loại gì?"
Đây là trục quan trọng quản lý **Persistence** và **Determinism**.
*   **DATA:** Tài sản (Asset). Cần lưu lại (Persist).
*   **SIGNAL:** Tín hiệu (Event). Tự động xóa sau khi dùng.
*   **META:** Thông tin gỡ lỗi (Debug). Không ảnh hưởng logic.
*   **HEAVY:** Dữ liệu lớn (Tensor, Image). Zero-copy, không rollback.

---

## 4.2. Giải phẫu Trục 3: Zone (Vùng An toàn)

Tại sao lại cần Zone?

Khi bạn lưu trạng thái hệ thống (Snapshot) để rollback, bạn có muốn lưu cả biến `tmp_image_buffer` nặng 5MB không? Không.
Khi bạn replay lại một bug, bạn có muốn replay lại cả lệnh `print("Debug...")` không? Không.

Zone giúp Engine phân loại rác và tài sản:

| Zone | Prefix | Tính chất | Persistence | Ví dụ |
| :--- | :--- | :--- | :--- | :--- |
| **DATA** | (None) | Business State | **Yes** | `user_id`, `cart_items` |
| **SIGNAL** | `sig_`, `cmd_` | Transient Event | **No** (Reset sau mỗi Step) | `sig_stop_machine`, `cmd_send_email` |
| **META** | `meta_` | Diagnostic Info | **No** (Optional Persist) | `meta_execution_time`, `meta_last_trace` |
| **HEAVY** | `heavy_` | Large/External Objects | **No** (Zero-copy, No rollback) | `heavy_model_weights`, `heavy_tensor` |

> **Note v3.0:** HEAVY zone dành cho các đối tượng không thể/không nên copy như Tensor, Model weights. Transaction sẽ **không tạo shadow** cho HEAVY objects và **không hỗ trợ rollback**. Đây là trade-off: tốc độ > atomicity.

---

## 4.3. Sự giao thoa (The Intersection)

Sức mạnh của Theus nằm ở giao điểm.

**Ví dụ: `domain_ctx.sig_login_success`**
*   **Layer:** Domain (Sống trong phiên làm việc).
*   **Zone:** Signal (Chỉ tồn tại trong tích tắc để kích hoạt Workflow khác).
*   **Semantic:** Output (Của process Login), Input (CỦA WORKFLOW - xử lý qua Flux DSL, không phải process).

---

## 4.4. Chiến lược Flattening (Phẳng hóa)

Một trong những hiểu lầm phổ biến là việc chia nhỏ Context thành 3 trục sẽ làm phức tạp code. Thực tế, Theus sử dụng chiến lược **"Phẳng hóa Bề mặt - Chặt chẽ Cốt lõi"**.

Dev không cần viết `ctx.layer.zone.semantic.value`.
Dev chỉ cần viết `ctx.domain_ctx.user_name`.

Engine sẽ tự động nội suy (Infer) Zone và Semantic dựa trên:
1.  Tên biến (Prefix `sig_` -> Signal, `heavy_` -> Heavy).
2.  Decorator `@process(outputs=[...])`.

> **⚠️ Lưu ý v3.0:** Contract paths bây giờ dùng `domain_ctx.*` thay vì `domain.*`.

---

## 4.5. Context Guard (Người gác cổng)

Khi Process chạy, Engine dựng lên một hàng rào ảo (Virtual Barrier) dựa trên 3 trục này.

*   Process chỉ khai báo `inputs=['domain_ctx.user']`.
*   Nếu code cố tình sửa `ctx.domain_ctx.user` -> **CRASH NGAY LẬP TỨC**.

Đây là cơ chế **"Zero Trust Memory"** (Bộ nhớ không tin cậy).

---

## 4.6. Context Schema (Bản vẽ kỹ thuật)

Trước khi code, bạn phải định nghĩa Schema.

```yaml
# specs/context_schema.yaml
context:
  domain_ctx:
    # DATA ZONE
    user_score: int
    
    # SIGNAL ZONE
    sig_user_clicked: bool
    
    # META ZONE
    meta_process_time: float
    
    # HEAVY ZONE
    heavy_embeddings: object
```

---

## 4.7. Hướng dẫn Hiện thực hóa (Implementation Standard)

Theus quy định tiêu chuẩn "Contract First" thông qua Python dataclasses:

```python
from dataclasses import dataclass, field
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class MyDomainContext(BaseDomainContext):
    # DATA ZONE
    user_score: int = 0
    
    # SIGNAL ZONE
    sig_user_clicked: bool = False
    
    # META ZONE
    meta_process_time: float = 0.0
    
    # HEAVY ZONE
    heavy_embeddings: object = None

@dataclass
class MyGlobalContext(BaseGlobalContext):
    max_limit: int = 1000

@dataclass
class MySystemContext(BaseSystemContext):
    domain_ctx: MyDomainContext = field(default_factory=MyDomainContext)
    global_ctx: MyGlobalContext = field(default_factory=MyGlobalContext)
```

*   **Lợi ích:** Developer và IDE có thể hiểu và validate dữ liệu.
*   **Runtime:** Engine sẽ đọc dataclass để validate cấu trúc bộ nhớ.
