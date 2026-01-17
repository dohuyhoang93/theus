# Chương 9: Hợp đồng Tin cậy (Theus Integrity Contracts)

---

## 9.1. Tại sao code cần "Hợp đồng"?

Hãy tưởng tượng bạn bước vào một nhà hàng sang trọng. Bạn xem thực đơn (Input), gọi món, và đầu bếp chế biến ra món ăn (Output). Nếu nhà hàng không có thực đơn, bạn sẽ phải vào tận bếp để hỏi xem có nguyên liệu gì. Đó là sự hỗn loạn.

Trong lập trình Theus, **Contract** là bản cam kết công khai của Process: *"Tôi cần gì, Tôi làm gì, và Tôi trả lại gì."*

Theus nâng tầm Contract lên thành **Luật (Law)**. Không giống như Type Hint trong Python (chỉ là gợi ý), Contract trong Theus được Engine **cưỡng chế (enforced)** tại Runtime.

---

## 9.2. Ba Trụ cột của Hợp đồng (The 3 Pillars of Contract)

Một Contract hợp lệ phải được xác định dựa trên **Ma trận An toàn 3 Trục** (xem Chương 4 và 12).

### **Pillar 1: Input Contract (Quyền Đọc)**
**Nguyên tắc:** *Pre-flight Check & Immutability.*
1.  **Khai báo toàn diện:** Process cấm truy cập bất kỳ biến nào không khai báo trong `inputs`.
2.  **Bất biến:** Dữ liệu Input bị Engine đóng băng (Frozen). Process chỉ được ĐỌC, không được SỬA.
    *   *Vi phạm:* `ctx.domain_ctx.user_id = 1` -> `ContractViolationError` (Illegal Write on Input).
3.  **Hạn chế Zone:** Cấm dùng `Signal` làm Input (vì Signal không ổn định).

### **Pillar 2: Output Contract (Quyền Ghi)**
**Nguyên tắc:** *Exclusive Mutation.*
1.  **Ghi đúng đích:** Process chỉ được ghi vào các field khai báo trong `outputs`.
2.  **Đảm bảo Type:** Theus check type của dữ liệu ghi ra so với Schema.
    *   *Vi phạm:* Ghi `str` vào field `int` -> `TypeError` (Audit Logged).

### **Pillar 3: Side-Effect Contract (Quyền Tác động)**
**Nguyên tắc:** *Managed I/O.*
1.  **Danh sách trắng (Whitelist):** Mọi tác động ra bên ngoài (API call, DB Write) phải được liệt kê.
2.  **Không logic ẩn:** Không được lén gọi `requests.get()` mà không khai báo.

---

## 9.3. Hệ thống Kiểm soát Lỗi (Error Contract)

Theus loại bỏ tư duy `try/catch` truyền thống. Lỗi là một phần của luồng dữ liệu.

### **Rule 1: Lỗi là Dữ liệu (Error as Data)**
Lỗi nghiệp vụ (Business Error) nên được xử lý như một kết quả hợp lệ.
*   Ví dụ: "Không tìm thấy mặt" là một kết quả, không phải là crash.
*   Process có thể raise exception đã khai báo trong `errors`.

### **Rule 2: Minh bạch khả năng lỗi**
Process phải khai báo: `errors=["ValueError", "INVALID_DATA"]`.
Điều này giúp Workflow Engine biết cách điều hướng (Rẽ nhánh khi gặp lỗi này).

---

## 9.4. Tòa án Tối cao: Audit Recipe (`audit_recipe.yaml`)

Ngoài Contract của từng Process, Theus giới thiệu một cơ chế kiểm soát toàn cục gọi là **Audit Recipe**. Đây là nơi định nghĩa các luật lệ "siêu cấp" mà mọi Process phải tuân theo.

> **⚠️ Lưu ý v3.0:** Paths trong audit recipe bây giờ dùng `domain_ctx.*` thay vì `domain.*`.

Ví dụ `specs/audit_recipe.yaml`:

```yaml
process_recipes:
  control_robot:
    inputs:
      # Luật: Không bao giờ được phép process nếu nhiệt độ lò > 1000
      - field: "temp"
        max: 1000
        level: "S"        # [S] = STOP (Emergency)
        message: "Lò quá nhiệt, nguy hiểm!"
        
      # Luật: Cảnh báo nếu pin yếu, nhưng vẫn cho chạy
      - field: "battery"
        min: 20
        level: "C"        # [C] = COUNT (Warning only)
        min_threshold: 0  # Báo ngay lập tức từ lần đầu
        
    outputs:
      # Luật: Tự động Block nếu logic cố tình xóa user_id
      - field: "domain_ctx.user_id"
        regex: ".+"       # Must not be empty
        level: "B"        # [B] = BLOCK (Soft Fail, Rollback)
        max_threshold: 3  # Cho phép sai 2 lần, lần 3 sẽ chặn
```

**Các mức độ hành động (Action Levels - v3.0):**
1.  **Level S (STOP):** Dừng khẩn cấp toàn hệ thống. Dành cho lỗi An toàn nghiêm trọng.
2.  **Level A (ABORT):** Dừng khẩn cấp workflow. Dành cho lỗi Logic nghiêm trọng.
3.  **Level B (BLOCK):** Hủy bỏ kết quả Transaction (Rollback), nhưng không làm sập App (Soft Fail).
4.  **Level C (COUNT):** Chỉ ghi log cảnh báo (Yellow Zone), hệ thống vẫn chạy tiếp.

**Cơ chế Thông minh (Smart Logic):**
*   **Dual Thresholds:** Bạn có thể đặt `min_threshold` (ngưỡng cảnh báo) và `max_threshold` (ngưỡng hành động).
*   **Cyclic Reset:** Bộ đếm lỗi sẽ tích lũy theo thời gian. Khi chạm ngưỡng `max_threshold`, hệ thống sẽ kích hoạt Action và **tự động Reset** bộ đếm về 0.

---

## 9.5. Ví dụ Contract Toàn diện (v3.0)

Dưới đây là một ví dụ mẫu mực về một Process Contract trong Theus v3.0:

```python
from theus.contracts import process, SemanticType

@process(
    # [1] Input: Chỉ đọc, Bất biến
    inputs=[
        "domain_ctx.vision.target_coords", 
        "global_ctx.config.safety_limits"  # Cross-layer read allowed
    ],
    
    # [2] Output: Quyền ghi độc quyền
    outputs=[
        "domain_ctx.robot.current_position",
        "domain_ctx.robot.status",
        "domain_ctx.sig_gripper_activated"  # Signal output OK
    ],
    
    # [3] Side-Effects: I/O ra thiết bị thật
    side_effects=["plc_controller"],
    
    # [4] Errors: Các khả năng thất bại
    errors=["ValueError", "TimeoutError"],
    
    # [5] Semantic Type
    semantic=SemanticType.EFFECT
)
def pick_item(ctx):
    """
    Điều khiển cánh tay robot gắp vật thể.
    """
    # Logic implementation...
    pass
```

> **Lời kết:** Contract không làm chậm Dev. Contract giúp Dev ngủ ngon vì biết rằng: **"Những gì mình không cho phép thì không thể xảy ra."**
