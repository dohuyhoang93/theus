# Chương 4: Thiết kế Dữ liệu (Context Design)

---

## 4.1. Tư duy 3 Trục (The 3-Axis Mindset)

Trong các thiết kế cũ, Context thường chỉ được chia theo "Phạm vi" (Layer). Tuy nhiên, để đáp ứng tiêu chuẩn an toàn công nghiệp, Context của Theus được cấu thành từ **3 Trục Tương giao (Three Intersecting Axes)**. Sự an toàn của hệ thống nằm chính tại giao điểm của ba trục này.

```
                                     [Y] SEMANTIC
                             (Input, Output, SideEffect, Error)
                                      ^
                                      |
                                      |
                                      |                +------+------+
                                      |               /|             /|
                                      +--------------+ |  CONTEXT   + |----------> [Z] ZONE
                                     /               | |  OBJECT    | |      (Data, Signal, Meta)
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
| **HEAVY** | `heavy_` | Large/External Objects | **No** (Log-only, Audit via introspection) | `heavy_model_weights`, `heavy_tensor` |

> **Note:** HEAVY zone dành cho các đối tượng không thể/không nên copy như Tensor, Model weights. Transaction sẽ không tạo shadow cho HEAVY objects, chỉ log mutations. Audit vẫn có thể kiểm tra qua introspection methods (`.mean()`, `.shape()`) được khai báo trong spec.

---

## 4.3. Sự giao thoa (The Intersection)

Sức mạnh của Theus nằm ở giao điểm.

**Ví dụ: `domain.sig_login_success`**
*   **Layer:** Domain (Sống trong phiên làm việc).
*   **Zone:** Signal (Chỉ tồn tại trong tích tắc để kích hoạt Workflow khác).
*   **Semantic:** Output (Của process Login), Input (Của process Notification).

---

## 4.4. Chiến lược Flattening (Phẳng hóa)

Một trong những hiểu lầm phổ biến là việc chia nhỏ Context thành 3 trục sẽ làm phức tạp code. Thực tế, Theus sử dụng chiến lược **"Phẳng hóa Bề mặt - Chặt chẽ Cốt lõi"**.

Dev không cần viết `ctx.layer.zone.semantic.value`.
Dev chỉ cần viết `ctx.domain.user_name`.

Engine sẽ tự động nội suy (Infer) Zone và Semantic dựa trên:
1.  Tên biến (Prefix `sig_` -> Signal).
2.  Decorator `@process(outputs=[...])`.

---

## 4.5. Context Guard (Người gác cổng)

Khi Process chạy, Engine dựng lên một hàng rào ảo (Virtual Barrier) dựa trên 3 trục này.

*   Process chỉ khai báo `inputs=['domain.user']`.
*   Nếu code cố tình sửa `ctx.domain.user` -> **CRASH NGAY LẬP TỨC**.

Đây là cơ chế **"Zero Trust Memory"** (Bộ nhớ không tin cậy).

---

## 4.6. Context Schema (Bản vẽ kỹ thuật)

Trước khi code, bạn phải định nghĩa Schema.

```yaml
# specs/context_schema.yaml
context:
  domain:
    # DATA ZONE
    user_score: int
    
    # SIGNAL ZONE
    sig_user_clicked: bool
    
    # META ZONE
    meta_process_time: float
```

---

## 4.7. Hướng dẫn Hiện thực hóa (Implementation Standard)

Theus quy định tiêu chuẩn "Contract First" thông qua `context_schema.yaml`:

1.  **Level 1 (Concept):** Định nghĩa Schema trong `specs/context_schema.yaml`. Đây là "Single Source of Truth".
2.  **Level 2 (Code):** Sử dụng `Python Dataclasses` để ánh xạ Schema vào code. Giúp IDE có thể gợi ý (Intellisense) và Type Check.
3.  **Level 3 (Validation):** Sử dụng các thư viện như `Pydantic` (Optional) nếu cần validation ở mức Field Level ngay khi khởi tạo.

## 4.8. Cấu hình "Single Source of Truth"
Thay vì định nghĩa rời rạc, file `specs/context_schema.yaml` đóng vai trò trung tâm:

```yaml
context:
  domain:
    user:
      name: {type: string}
      age: {type: integer, min: 18} # Static constraints
```

*   **Lợi ích:** Developer và Non-tech (như PM/BA) đều có thể đọc và hiểu dữ liệu.
*   **Runtime:** Engine sẽ đọc file này lúc khởi động để validate cấu trúc bộ nhớ.
