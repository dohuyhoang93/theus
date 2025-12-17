# Chương 5: Thiết kế Process (Process Design)

---

## 5.1. Định nghĩa Process trong POP

Trong kiến trúc POP, **Process** không đơn thuần là một hàm.
**Process là một đơn vị biến đổi dữ liệu có ý nghĩa độc lập.**

Công thức chính thức (Spec Chapter 4):
```
Process = Semantic Unit of Transformation
```

Một Process hợp lệ phải thỏa mãn tiêu chí: **Được mô tả bằng một mệnh đề đơn không mơ hồ.**

---

## 5.2. Nguyên tắc Phân rã Process Phi-Nhị-Nguyên (NB-PDR)

Để tránh cực đoan (Process quá nhỏ vụn vặt hoặc quá lớn khổng lồ), POP cung cấp hệ thống 7 quy tắc phân rã (Decomposition Rules):

### **Rule 1: Phân rã theo Khối Ý Nghĩa (Semantic Cluster)**
Một Process không nhất thiết chỉ chứa một dòng code. Nó có thể chứa một cụm logic (Cluster) miễn là cụm đó phục vụ **một mục đích chung**.
*   *Hợp lệ:* `detect_object_pose` (bao gồm tiền xử lý, phân đoạn, tính toán).
*   *Vi phạm:* `detect_pose_and_save_db` (hai mục đích khác nhau: Tính toán & Lưu trữ).

### **Rule 2: Khả năng Giải thích (Explainability)**
Nếu bạn không thể mô tả Process bằng một câu đơn có cấu trúc **Chủ ngữ - Động từ - Bổ ngữ**, Process đó cần được phân rã.
*   *Sai:* "Hàm này xử lý dữ liệu đầu vào rồi tùy vào cấu hình mà tính toán hoặc gọi API." (Câu phức, nhiều điều kiện).
*   *Đúng:* "Hàm này chuẩn hóa dữ liệu đầu vào."

### **Rule 3: Độ biến động (Volatility)**
Tách phần logic thường xuyên thay đổi (Business Rules) ra khỏi phần logic ổn định (Core/Infrastructure).
*   *Ví dụ:* Tách `calculate_discount` (thay đổi theo mùa) ra khỏi `create_invoice` (ổn định).

### **Rule 4: Cách ly Rủi ro (Risk Segregation)**
Tách các tác vụ có mức độ rủi ro khác nhau.
*   **High Risk (I/O, External API):** Cần cô lập để handle lỗi riêng.
*   **Pure Logic (Math):** Cần giữ sạch để dễ unit test.
*   *Không được trộn lẫn:* Việc gọi API thanh toán (có thể fail) không được nằm chung với việc tính tổng tiền (logic thuần túy).

### **Rule 5: Rẽ nhánh Minh bạch (Transparent Branching)**
POP cho phép `if/else` trong Process, NHƯNG nhánh đó phải minh bạch về mặt ngữ nghĩa.
*   *Hợp lệ:* `if pressure > limit: raise Alarm`. (Logic nghiệp vụ rõ ràng).
*   *Vi phạm:* `if type(x) == str: return int(x)`. (Logic sửa lỗi ngầm ẩn - Implicit Casting).

### **Rule 6: Sử dụng Local Context**
Process được quyền sử dụng tự do `Local Context` để lưu biến tạm. Điều này giúp Process phức tạp không làm "bẩn" Domain Context nhưng vẫn giữ được sự trong sáng của logic.

### **Rule 7: Tải Nhận thức (Cognitive Load)**
Đây là quy tắc tối cao: **Nếu một Process làm developer phải dừng lại quá 5 giây để hiểu nó làm gì, hãy chia nhỏ nó.**
Độ phức tạp của code không đo bằng số dòng, mà đo bằng nỗ lực não bộ để dựng lại mô hình mental model của nó.

---

## 5.3. Quy tắc An toàn Tương tác (Interaction Safety Rules)

Ngoài việc phân rã, POP đặt ra 4 quy tắc nghiêm ngặt để đảm bảo Process không phá hoại Context (Spec Chapter 5):

### **Rule 1: Khai báo Truy cập Minh bạch (Explicit Context Access)**
Process phải khai báo rõ phần nào của Context mà nó cần đọc (Read) và phần nào nó sẽ ghi (Write).
*   *Yêu cầu:* Code phải thể hiện rõ intent.
*   *Ví dụ:* `read: ctx.domain.pose`, `write: ctx.domain.collision_risk`.

### **Rule 2: Biện minh Nghiệp vụ (Domain Justification)**
Mọi thay đổi trên Domain Context phải có lý do xuất phát từ logic nghiệp vụ.
*   *Cấm:* Xóa field `target_pose` chỉ vì "code cho gọn" hoặc "tiết kiệm RAM". Domain Context là sự thật, không phải là biến tạm.

### **Rule 3: Bất biến Toàn cục (Global Invariance)**
**Global Context là Read-Only đối với Process.**
Process không được phép thay đổi các giá trị toàn cục (Config, Job ID). Nếu cần thay đổi hành vi hệ thống, hãy dùng cờ hiệu (Flags) trong Domain Context hoặc khởi tạo một Workflow mới.

### **Rule 4: Biến đổi Quan sát được (Observable Mutation)**
Sự thay đổi của Context trước và sau Process phải là **Delta** rõ ràng.
*   *Trước:* `status = PENDING`
*   *Sau:* `status = VERIFIED`
*   *Delta:* Trạng thái đã được xác thực.
*   *Cấm:* Thay đổi ngầm các field không liên quan hoặc thay đổi cấu trúc dữ liệu mà không thông qua cơ chế Versioning.

---

## 5.4. Kết cấu chuẩn của một Process

Một Process chuẩn mực trong POP nên tuân theo cấu trúc "Sandwich":

1.  **Preparation (Đầu vào):** Đọc dữ liệu từ Domain Context hoặc Local Context.
2.  **Execution (Lõi logic):** Thực hiện biến đổi (Pure Function hoặc I/O call qua Adapter).
3.  **Update (Đầu ra):** Cập nhật kết quả vào Domain Context (tuân thủ Rule 2 & 4).

> **Lời khuyên:** Hãy viết Process như thể nó là một "Hộp đen minh bạch" (Transparent Blackbox) - Bên ngoài nhìn vào thấy rõ đầu vào/ra, bên trong gói gọn sự phức tạp.

---

## 5.5. Hướng dẫn Hiện thực hóa (Implementation - V2 Standard)

Trong POP V2, Process được hiện thực hóa bằng Python Decorator `@process` để đảm bảo thực thi Contract:

```python
from pop.contracts import process

@process(
    inputs=["domain.user.age", "domain.order.amount"], 
    outputs=["domain.order.is_valid"],
    errors=["VALUE_ERROR"]
)
def validate_order(ctx):
    # 1. Preparation (Context -> Local)
    age = ctx.domain.user.age
    
    # 2. Logic
    if age < 18:
        raise ValueError("Underage")
        
    # 3. Update (Local -> Context)
    ctx.domain.order.is_valid = True
```

*   **Decorator `@process`:** Đóng vai trò là "Bản cam kết" (Contract). Engine sử dụng thông tin này để dựng "Hàng rào bảo vệ" (Context Guard) trước khi hàm chạy.
*   **Pure Python:** Không cần kế thừa Class phức tạp. Chỉ cần hàm thuần túy.

> **Hỏi: Tại sao không đưa Input/Output ra file YAML?**
>
> **Đáp:** POP phân định rõ 3 loại Contract:
> 1.  **Structure Contract (`context_schema.yaml`):** Định nghĩa Data (Type, Shape).
> 2.  **Governance Contract (`audit_recipe.yaml`):** Định nghĩa Chất lượng (Quality, Thresholds).
> 3.  **Dependency Contract (`@process` decorator):** Định nghĩa **Logic Code cần gì**.
>
> Việc để Dependency ngay trên đầu hàm (Decorator) tuân thủ nguyên tắc **Locality of Behavior**. Khi bạn sửa code bên trong hàm (ví dụ đổi từ dùng `user.age` sang `user.dob`), bạn sửa ngay decorator bên trên. Nếu để ở file YAML rời rạc, code và config sẽ dễ bị lệch pha (Drift).
