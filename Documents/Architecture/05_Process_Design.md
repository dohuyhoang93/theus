# Chương 5: Thiết kế Process (Theus Process Design)

---

## 5.1. Định nghĩa Process trong Theus

Trong hệ sinh thái Theus, **Process** không đơn thuần là một hàm Python.
**Process là một đơn vị biến đổi dữ liệu thuần túy (Pure Unit of Transformation).**

Công thức cốt lõi:
```
Process(Context_Snapshot) -> Context_Delta
```

Một Process hợp lệ phải thỏa mãn:
1.  **Atomic (Nguyên tử):** Thực hiện trọn vẹn hoặc không làm gì cả.
2.  **Stateless (Phi trạng thái):** Không lưu giữ biến nội tại giữa các lần gọi (trừ khi dùng `Local Context` cho tính toán tạm).
3.  **Contract-bound (Ràng buộc hợp đồng):** Phải khai báo trước input/output/side-effect.

---

## 5.2. Nguyên tắc Phân rã Process (The 7 Rules)

Để xây dựng hệ thống bền vững, Theus kế thừa nguyên tắc phân rã của POP:

### **Rule 1: Khối Ý Nghĩa (Semantic Cluster)**
Một Process chứa một cụm logic phục vụ **một mục đích chung**.
*   *Hợp lệ:* `analyze_market_trend` (gồm lấy dữ liệu, tính toán chỉ số, ra quyết định).
*   *Vi phạm:* `calculate_and_email` (trộn lẫn tính toán và I/O).

### **Rule 2: Khả năng Giải thích (Explainability)**
Nếu không thể mô tả Process bằng cấu trúc **"Chủ ngữ + Động từ + Bổ ngữ"**, hãy chia nhỏ nó.
*   *Tốt:* "Process này chuẩn hóa dữ liệu người dùng."
*   *Tệ:* "Process này kiểm tra config, nếu đúng thì tính toán, sai thì log lỗi."

### **Rule 3: Tách biệt Biến động (Volatility Separation)**
Tách logic thường xuyên thay đổi (Business Rules) khỏi logic hạ tầng ổn định.

### **Rule 4: Cô lập Rủi ro (Risk Isolation)**
Tách các tác vụ I/O (dễ lỗi) ra khỏi logic tính toán (Pure Logic).
*   *Ví dụ:* Process A lấy dữ liệu từ API (Risk cao). Process B tính toán trên dữ liệu đó (Risk thấp).

### **Rule 5: Rẽ nhánh Minh bạch (Transparent Branching)**
`If/else` phải dựa trên dữ liệu nghiệp vụ rõ ràng, không dựa trên trạng thái ẩn.

### **Rule 6: Sử dụng Local Context**
Dùng `Local Context` cho các biến tạm để giữ `Domain Context` sạch sẽ.

### **Rule 7: Tải Nhận thức (Cognitive Load)**
**Quy tắc tối cao:** Nếu developer mất quá 5 giây để hiểu Process làm gì -> Refactor ngay lập tức.

---

---

## 5.3. Quy tắc An toàn Tương tác (Interaction Matrix)

Đây là điểm khác biệt lớn nhất của **Theus Framework**. Process không "tự do" truy cập Context. Nó bị kiểm soát bởi **Ma trận An toàn 3 Trục**:

### **Rule 1: Khai báo Phải Đúng Zone**
*   **CẤM:** Dùng `Signal` làm `Input` (Vì Signal không Replay được).
*   **CẤM:** Dùng `Meta` để điều hướng logic nghiệp vụ.

### **Rule 2: Bất biến Input (Input Immutability)**
*   Dữ liệu trong list `inputs` bị Engine "đóng băng" (Frozen).
*   Process chỉ được **ĐỌC**. Cố tình ghi -> `ContractViolationError`.

### **Rule 3: Độc quyền Output (Output Exclusivity)**
*   Process chỉ được ghi vào những field đã khai báo trong `outputs`.
*   Mọi thay đổi khác lên Context đều bị Engine từ chối và Rollback.

### **Rule 4: Side-Effect Tường minh**
*   Mọi tương tác I/O (Database, API, File) phải được khai báo trong `side_effects`.
*   Theus sẽ wrap các wrapper này để đo lường và audit.

---

## 5.4. Hướng dẫn Hiện thực hóa (Standard Implementation)

Trong Theus Framework, chúng ta sử dụng decorator `@process` từ thư viện `theus`:

```python
from theus import process

@process(
    inputs=["domain.user.age", "domain.cart.total"], 
    outputs=["domain.order.status", "domain.order.discount"],
    side_effects=[],
    errors=["INVALID_AGE"]
)
def validate_order(ctx):
    # 1. Preparation (Read from Input)
    age = ctx.domain.user.age
    total = ctx.domain.cart.total
    
    # 2. Pure Logic (Validate Rule)
    if age < 18:
        # Business Error (Not Exception)
        return ctx.fail("INVALID_AGE")
        
    discount = 0.0
    if total > 1000:
        discount = 0.1
        
    # 3. Update (Write to Output)
    ctx.domain.order.status = "VALID"
    ctx.domain.order.discount = discount
    
    # Implicit Return Success
```

### Tại sao lại cần Decorator dài dòng thế?
1.  **Runtime Guard:** Engine đọc decorator để dựng hàng rào bảo vệ (ContextGuard).
2.  **Auto Documentation:** Từ code, ta có thể generate ra biểu đồ luồng dữ liệu (Data Lineage).
3.  **Audit Trail:** Khi có lỗi, Audit Log sẽ ghi: *"Process `validate_order` thất bại vì Input `age=15`"*.

> **Tư duy Theus:** Developer không viết "code chạy việc". Developer viết "mô tả logic" và Engine sẽ chạy nó một cách an toàn.
