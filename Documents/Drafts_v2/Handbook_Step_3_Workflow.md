# Bước 3: Dòng chảy được Điều phối (Orchestrated Flow)

---

## 3.1. Chuyện nhà Dev: "Kim tự tháp If/Else"

Bạn đã có Context (Dữ liệu) và Process (Hàm). Giờ là lúc ghép chúng lại.
Cách làm cũ (Hardcoded):

```python
# main.py
def run_app():
    if check_user():
        if validate_order():
             process_payment()
             send_email()
        else:
             log_error()
    else:
        return "403"
```

Vấn đề:
1.  **Cứng nhắc:** Sếp bảo "Tắt gửi email vào cuối tuần nhé", bạn phải sửa code `main.py`.
2.  **Khó đọc:** Logic nghiệp vụ (Flow) bị chôn vùi trong cú pháp ngôn ngữ.
3.  **Khó tái sử dụng:** Bạn không thể bốc tách chuỗi `validate -> payment` sang chỗ khác.

---

## 3.2. Giải pháp POP: Dây chuyền Lắp ráp (Assembly Line)

POP tách biệt hoàn toàn **"Việc cần làm" (Process)** và **"Thứ tự làm" (Workflow)**.
*   **Process** là công nhân chuyên biệt (chỉ biết hàn, chỉ biết sơn).
*   **Workflow** là bản vẽ dây chuyền.
*   **Engine** là người quản xưởng, đọc bản vẽ và chỉ đạo công nhân.

---

## 3.3. Thực hành: Bản vẽ YAML

Chúng ta dùng YAML để định nghĩa luồng đi. Đây là ngôn ngữ khai báo (Declarative).

### **Bước A: Định nghĩa Workflow**
Tạo file `workflows/checkout_flow.yaml`. Lưu ý rằng Engine V1 hiện tại hỗ trợ luồng tuyến tính (Linear):

```yaml
name: "Checkout Process"
description: "Quy trình thanh toán tiêu chuẩn"

steps:
  # Bước 1: Kiểm tra
  - step: validate_user_active
  - step: validate_stock_item
  
  # Bước 2: Tính toán
  - step: calculate_discount_vip
  - step: apply_shipping_fee
  
  # Bước 3: Chốt đơn
  - step: reserve_stock_in_db
  - step: deduct_user_balance
```

### **Bước B: Lắp ráp trong `main.py` (Quan trọng!)**
Process viết ra không tự chạy. Bạn phải "Đăng ký" (Register) nó với Engine thì Engine mới biết tên mà gọi.

```python
# main.py
from pop import POPEngine
from src.context import SystemContext
# Import các process
from src.processes import p_validation, p_calculation, p_payment

# 1. Khởi tạo
ctx = SystemContext()
engine = POPEngine(ctx)

# 2. Đăng ký Công nhân (Registration)
# Nếu không đăng ký, file YAML sẽ báo lỗi "Process Not Found"
engine.register_process("validate_user_active", p_validation.validate_user_active)
engine.register_process("validate_stock_item", p_validation.validate_stock_item)
engine.register_process("calculate_discount_vip", p_calculation.calculate_discount_vip)
# ... đăng ký hết các step ...

# 3. Load & Chạy
engine.execute_workflow("workflows/checkout_flow.yaml")
```

---

## 3.4. Năng lực & Vận hành Engine (Engine Capabilities)

Trước khi đi xa hơn, hãy hiểu rõ cỗ máy bạn đang lái:

### **1. Khả năng (Capabilities)**
*   **Linear Execution:** Phiên bản Engine hiện tại chạy tuần tự từ trên xuống dưới.
*   **Atomic Steps:** Mỗi bước (Process) là một Transaction. Nếu nó thành công -> Commit dữ liệu.
*   **Fail-Fast:** Nếu một bước gặp lỗi (Exception), Engine sẽ **Rollback** thay đổi của bước đó và **Dừng lại ngay lập tức**. Nó không tự động bỏ qua hay retry (trừ khi bạn code logic retry trong process).

### **2. Giới hạn (Limitations)**
*   **Chưa có Rẽ nhánh (No Branching in YAML):** Bạn không thể viết `if: success then step_B` trong YAML lúc này. Rẽ nhánh phải được xử lý bên trong Logic của Process hoặc dùng cơ chế Advanced (sẽ bàn ở Bước 5).
*   **Chưa có Song song (No Parallel):** Các bước chạy lần lượt, không chạy đồng thời.

### **3. Kiểm soát & Vận hành**
*   **Monitoring:** Engine không có Dashboard UI. Bạn giám sát qua Logs (Side-effects) hoặc inspect Context sau khi chạy xong.
*   **Stopping:** Để dừng khẩn cấp, chỉ có cách can thiệp hệ thống (Ctrl+C hoặc Kill Signal). Engine không có nút "Pause".

---

## 3.5. Tổng kết Bước 3

*   **Workflow YAML** làm cho logic nghiệp vụ trong sáng, dễ đọc.
*   **Registration** là bước bắt buộc để kết nối Code và YAML.
*   **Engine** hoạt động theo nguyên tắc "An toàn tuyệt đối": Lỗi là Dừng, không cố chạy tiếp sai lệch.

**Thử thách:** Hãy thử đổi thứ tự `apply_shipping_fee` lên trước `calculate_discount` trong YAML. Chạy lại và xem kết quả tính toán thay đổi thế nào mà không cần sửa code Python!
