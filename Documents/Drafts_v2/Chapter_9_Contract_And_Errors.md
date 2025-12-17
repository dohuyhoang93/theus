# Chương 9: Hợp đồng Tin cậy (The Contract of Trust)

---

## 9.1. Tại sao code cần "Hợp đồng"?

Hãy tưởng tượng bạn bước vào một nhà hàng sang trọng. Bạn xem thực đơn (Menu - Input), gọi món, và đầu bếp chế biến ra món ăn (Output). Nếu nhà hàng không có thực đơn, bạn sẽ phải vào tận bếp để hỏi xem có nguyên liệu gì. Đó là sự hỗn loạn.

Trong lập trình cũng vậy. Một Process không có Contract giống như một nhà hàng không thực đơn. Người đọc code (và cả Engine) phải "vào tận bếp" (đọc từng dòng code xử lý) mới biết nó cần biến `user_id` hay `order_id`.

**POP giải quyết vấn đề này bằng Process Contract.**
> **Contract là bản cam kết công khai:** "Tôi cần gì, Tôi làm gì, và Tôi trả lại gì."

Lợi ích cốt lõi không chỉ là "chạy đúng", mà là **giảm tải nhận thức (Cognitive Load)**. Bạn tin tưởng contract, bạn không cần đọc code bên trong.

---

## 9.2. Quy tắc 1: Input Contract (Đầu vào)

Để Process hoạt động an toàn, POP quy định 3 nguyên tắc bất di bất dịch cho đầu vào:

### **Rule 1.1: Khai báo toàn diện (Total Declaration)**
Tất cả những gì Process cần để chạy (từ biến user, config, đến tham số ngưỡng) đều phải được liệt kê trong danh sách `input`.
*   *Chi tiết:* Cấm tuyệt đối việc "đi cửa sau" – tức là truy cập các biến global hoặc các field trong Context mà không khai báo.

### **Rule 1.2: Kiểm tra Tiền quyết (Pre-flight Check)**
Input phải tồn tại và đúng kiểu **trước khi** Process chạy.
*   *Cơ chế:* Engine sẽ đóng vai trò "người gác cổng". Nếu thiếu nguyên liệu, Engine sẽ từ chối chạy Process ngay lập tức (Fail Fast).

### **Rule 1.3: Bất biến (Immutability)**
Process chỉ được **ĐỌC** Input, không được **SỬA** nó.
*   *Lý do:* Nếu bạn đưa gạo cho đầu bếp, đầu bếp trả lại cơm. Gạo vẫn là gạo (trong kho), cơm là vật thể mới. Việc giữ Input bất biến giúp ta dễ dàng truy vết (audit) dữ liệu gốc.

> **Tại sao cần khắt khe vậy?**
> Để đảm bảo **Zero Surprise**. Sẽ không có chuyện code chạy được 50% rồi mới crash vì thiếu dữ liệu `user_settings` bị null.

---

## 9.3. Quy tắc 2: Output Contract (Đầu ra)

Process trả dữ liệu về Context cũng cần tuân thủ kỷ luật nghiêm ngặt:

### **Rule 2.1: Ghi đúng đích danh (Target Locking)**
Process chỉ được phép ghi vào các field đã hứa trong `output`.
*   *Cơ chế:* Engine sẽ khoá toàn bộ Context, chỉ cấp quyền ghi (Write Permission) cho những vị trí được khai báo.

### **Rule 2.2: Rỗng tường minh (Explicit Empty)**
Nếu Process chỉ tính toán hoặc gửi email mà không ghi gì lại Context, nó phải khai báo `output: []`.
*   *Ý nghĩa:* Để phân biệt rõ ràng giữa "Tôi không ghi gì cả" và "Tôi quên khai báo".

### **Rule 2.3: Ngữ nghĩa đúng (Semantic Consistency)**
Dữ liệu ghi ra phải khớp với ý nghĩa của field đó trong Domain. Không được ghi `string` vào chỗ của `int`, hoặc ghi `Error Object` vào chỗ của `User Data`.

> **Tại sao cần khắt khe vậy?**
> Để bảo vệ **Sự toàn vẹn của Dữ liệu (Data Integrity)**. Không một Process lỗi nào có thể vô tình ghi đè và làm hỏng dữ liệu của các Process khác.

---

## 9.4. Quy tắc 3: Side-Effect Contract (Tác động bên ngoài)

Khi Process cần gọi Database, Camera, hay API, đó là Side-Effect.

### **Rule 3.1: Danh sách trắng (Whitelisting)**
Mọi hành động I/O phải được liệt kê rõ: `uses: ["camera", "db_sql"]`.

### **Rule 3.2: Chỉ dùng Env (Via Environment)**
Must use: `env.camera.read()`.
Cấm: `import cv2; cv2.VideoCapture(0)`.
*   *Lý do:* Để Engine kiểm soát được luồng I/O và hỗ trợ Mocking khi test.

### **Rule 3.3: Không logic ẩn (No Hidden Retry)**
Các cơ chế như Retry, Timeout phải được cấu hình công khai, không hard-code `while True` trong code.

---

## 9.5. Quy tắc 4: Error Contract (Hợp đồng Lỗi)

Cách POP xử lý lỗi khác hoàn toàn với `try/catch` truyền thống.

### **Rule 4.1: Lỗi là dữ liệu (Error as Data)**
Lỗi nghiệp vụ (Business Error) không phải là Exception. Nó là một trạng thái hợp lệ.
*   Ví dụ: "Không tìm thấy mặt" là một kết quả, không phải là một tai nạn.
*   Process phải trả về mã lỗi: `return Fail("FACE_NOT_FOUND")`.

### **Rule 4.2: Minh bạch các khả năng lỗi**
Process phải liệt kê các mã lỗi nó có thể trả về: `errors: ["TIMEOUT", "INVALID_DATA"]`.
*   *Lợi ích:* Người thiết kế Workflow có thể nhìn vào danh sách này để vẽ các nhánh xử lý (Fallback) phù hợp.

### **Rule 4.3: Không Exception "Ma" (No Ghosts)**
Process không được để lọt các Exception không khai báo ra ngoài (trừ các lỗi hệ thống như OutOfMemory). Mọi Exception phải được bắt (catch) và chuyển đổi thành Error Code.

---

## 9.6. Vai trò của Engine: Người Bảo Hộ (The Guardian)

Engine không phải là cảnh sát bắt bớ, mà là người bảo hộ sự an toàn cho hệ thống.

1.  **Validate:** Trước khi chạy, Engine rà soát xem "Nguyên liệu (Input)" đã đủ chưa.
2.  **Sandbox:** Khi chạy, Engine tạo một môi trường cách ly, đảm bảo Process không thể vọc vạch lung tung.
3.  **Audit:** Sau khi chạy, Engine ghi lại nhật ký: "Process A đã lấy X, tạo ra Y, và gặp lỗi Z".

---

## 9.7. Ví dụ Contract Đầy đủ (Full Spec)

Dưới đây là một ví dụ minh họa cách viết Contract trong thực tế (dữ liệu YAML hoặc Docstring):

```yaml
process: robot.pick_item
description: "Điều khiển cánh tay robot gắp vật thể tại tọa độ cho trước"

# 1. Input: Cần gì?
input:
  - path: "ctx.vision.target_coordinates"
    type: "Point3D"
    desc: "Tọa độ vật thể nhận từ Camera"
  - path: "ctx.config.safety_limits"
    type: "BoxLimits"

# 2. Output: Sẽ tạo ra gì?
output:
  - path: "ctx.robot.last_action_status"
    type: "Enum(SUCCESS, FAIL)"
  - path: "ctx.robot.current_position"
    type: "Point3D" # Cập nhật vị trí mới sau khi gắp

# 3. Side-Effects: Dùng đồ nghề gì?
side_effects:
  - resource: "plc_controller"
    action: "send_gcode_command"

# 4. Errors: Có thể hỏng ở đâu?
errors:
  - code: "OUT_OF_REACH"
    condition: "Tọa độ đích nằm ngoài Safety Limits"
  - code: "GRIPPER_JAMMED"
    condition: "PLC báo kẹt kẹp, không đóng được"
```
