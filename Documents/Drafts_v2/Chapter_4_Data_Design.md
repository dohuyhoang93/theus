# Chương 4: Thiết kế Dữ liệu (Context First Design)

---

## 4.1. Nguyên lý Context First

Trong POP, Context không phải là một biến `dict` tùy tiện. Nó là "Bản đồ của Thế giới Logic".
Nguyên lý Context First yêu cầu:
**"Định nghĩa cấu trúc dữ liệu là bước đầu tiên của mọi quy trình thiết kế, trước khi viết bất kỳ dòng logic nào."**

---

## 4.2. Chiến lược Phân vùng Dữ liệu 3 Lớp (The 3-Layer Context Model)

Để tránh "God Context" (Context khổng lồ chứa mọi thứ), POP quy định cấu trúc dữ liệu gồm 3 lớp rõ ràng (Spec Chapter 2):

```
┌───────────────────────────────────┐
│          Global Context           │
└───────────────┬───────────────────┘
                │
                ▼
       ┌───────────────────┐
       │   Domain Context  │
       └────────┬──────────┘
                │
    ┌───────────┴───────────┐
    │          Process       │
    └───────────┬───────────┘
                │
                ▼
       ┌───────────────────┐
       │   Local Context   │
       └───────────────────┘
```

### 4.2.1. Global Context (Bộ Xương Sống)
*   **Định nghĩa:** Chứa dữ liệu cấu trúc (metadata) xuyên suốt toàn bộ vòng đời ứng dụng, không phụ thuộc vào một process cụ thể nào.
*   **Tính chất:** Ổn định (Stable), đọc nhiều hơn ghi (Read-heavy).
*   **Ví dụ:** `job_id`, `timestamp`, `user_id`, `pipeline_config`.
*   **Quy tắc:**
    *   Không chứa dữ liệu nghiệp vụ (Domain Logic).
    *   Không chứa dữ liệu ngắn hạn (Temporary State).
    *   Đóng vai trò "Thông tin nhận diện" cho toàn hệ thống.

### 4.2.2. Domain Context (Trái Tim)
*   **Định nghĩa:** Chứa trạng thái nghiệp vụ thực tế của workflow ("The Truth").
*   **Tính chất:** Biến thiên theo từng bước xử lý (Mutable), nhưng phải tuân thủ nghiêm ngặt quy tắc Semantic.
*   **Ví dụ:** `TargetPose`, `TransactionStatus`, `ModelOutput`.
*   **Quy tắc:** Là nơi duy nhất phản ánh sự tiến hóa của logic. Trước và sau mỗi Process, Domain Context phải giữ được tính nhất quán.

### 4.2.3. Local Context (Tế Bào)
*   **Định nghĩa:** Chứa biến tạm, buffer tính toán phục vụ riêng cho một Process.
*   **Tính chất:** Ngắn hạn (Ephemeral), tự hủy sau khi Process kết thúc.
*   **Ví dụ:** `temp_buffer`, `raw_sensor_bytes`, `loop_counter`.
*   **Quy tắc:** Tuyệt đối không được "lây nhiễm" (leak) sang Global hoặc Domain.


---

## 4.3. Sáu Quy luật Vận động của Context (The 6 Context Rules)

Để đảm bảo tính bền vững của kiến trúc, POP áp đặt 6 quy luật bất biến cho Context (được trích xuất từ Spec Chapter 3):

### **Rule 1: Phân định ranh giới (Boundary definition)**
Mọi trường dữ liệu (Field) phải được định danh rõ ràng là thuộc **Domain** hay **Local**. Không có vùng xám.

### **Rule 2: Tính mục đích (Purposefulness)**
Dữ liệu chỉ được nằm trong Domain Context nếu nó phục vụ trực tiếp cho Domain Logic. Dữ liệu thô (`temp_buffer`, `raw_bytes`) phải nằm ở Local.

### **Rule 3: Bảo toàn dữ liệu (Data Preservation)**
Không Process nào được phép xóa hoặc ghi đè (override) dữ liệu Domain mà không có lý do nghiệp vụ rõ ràng.
*   *Vi phạm:* Process A xóa field `user_id` chỉ để tiết kiệm bộ nhớ.
*   *Hợp lệ:* Process B chuyển `order_status` từ `PENDING` sang `PAID` (đây là biến đổi trạng thái).

### **Rule 4: Semantic Versioning**
Bất kỳ thay đổi nào về cấu trúc (Schema) của Domain Context phải đi kèm với việc nâng version của Context.

### **Rule 5: Cách ly Local (Local Isolation)**
`Local Context` **TUYỆT ĐỐI KHÔNG** được hòa nhập vào `Domain Context`. Vùng làm việc tạm thời phải được hủy sau khi Process kết thúc.

### **Rule 6: Nhất quán Ngữ nghĩa (Semantic Consistency)**
Một tên trường (Field Name) phải giữ nguyên ý nghĩa trong suốt vòng đời Workflow. Không được dùng lại field `pressure` để lưu giá trị `temperature`.

---

## 4.4. Bộ Kiểm Tra Tiến Hóa (Context Evolution Safety)

Với mỗi thay đổi trên Context, Kiến trúc sư phải trả lời 5 câu hỏi (Evolution Checklist):
1.  **Q1 (Domain):** Field mới này có phục vụ Business Logic không?
2.  **Q2 (Ambiguity):** Tên gọi có gây hiểu nhầm với các field cũ không?
3.  **Q3 (Impact):** Việc thay đổi này có làm gãy vỡ các Process phía sau không?
4.  **Q4 (Versioning):** Có cần nâng version schema không?
5.  **Q5 (Transparency):** Người đọc code có hiểu ngay ý nghĩa của dữ liệu này không?

---

## 4.5. Quy tắc Đồng đẳng Context (Context Parity)

> *"Context trước và sau một Process phải so sánh được về mặt ý nghĩa."*

Điều này có nghĩa là một Process không được phép làm Context "biến thái" sang một dạng hoàn toàn khác (ví dụ: Input là `Image`, Output là `SQLConnection`) trừ khi đó là mục đích đã định nghĩa rõ của Process.

---

## 4.6. Hướng dẫn Hiện thực hóa (Implementation - V2 Standard)

POP V2 quy định tiêu chuẩn "Contract First" thông qua `context_schema.yaml`:

1.  **Level 1 (Concept):** Định nghĩa Schema trong `specs/context_schema.yaml`. Đây là "Single Source of Truth".
2.  **Level 2 (Code):** Sử dụng `Python Dataclasses` để ánh xạ Schema vào code. Giúp IDE có thể gợi ý (Intellisense) và Type Check.
3.  **Level 3 (Validation):** Sử dụng các thư viện như `Pydantic` (Optional) nếu cần validation ở mức Field Level ngay khi khởi tạo.

## 4.7. Cấu hình "Single Source of Truth"
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
