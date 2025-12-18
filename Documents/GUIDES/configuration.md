# Hướng dẫn Cấu hình Theus V2.1

Tài liệu này giải thích chi tiết cú pháp và cấu trúc của các tệp cấu hình chính trong Theus V2.1: `workflow.yaml` và `audit_recipe.yaml`.

---

## 1. Workflow Configuration (`specs/workflow.yaml`)

File này định nghĩa **Logic Điều phối** (Orchestration Logic) của ứng dụng. Theus V2.1 sử dụng mô hình **Hybrid Workflow** kết hợp giữa Finite State Machine (FSM) và Linear Chain.

### Cấu trúc Cơ bản

```yaml
name: "Tên Workflow"
initial_state: "TRẠNG_THÁI_BẮT_ĐẦU" # (Optional, mặc định là State đầu tiên)

states:
  STATE_NAME:
    # 1. Entry Action: Chạy chuỗi tuần tự khi vào state
    entry: ["process_1", "process_2", ...] 
    
    # 2. Transitions: Chuyển trạng thái dựa trên Signal
    "on":
      SIGNAL_NAME: "TARGET_STATE"
```

### Chi tiết Thành phần

#### 1.1 `entry` (Linear Chain)
- Là một danh sách các tên Process (được đăng ký trong `app.py`).
- Khi FSM chuyển vào trạng thái này, `ThreadExecutor` sẽ chạy tuần tự các process này trong một **Thread** riêng.
- Nếu chuỗi chạy thành công -> Hệ thống tự động phát Event `EVT_CHAIN_DONE`.
- Nếu có Process lỗi hoặc Crash -> Hệ thống tự động phát Event `EVT_CHAIN_FAIL`.

#### 1.2 `"on"` (Transitions)
- Định nghĩa quy tắc chuyển trạng thái.
- **LƯU Ý QUAN TRỌNG:** Phải để từ khóa `"on"` trong dấu ngoặc kép.
  - Lý do: Một số bộ parser YAML (theo chuẩn Nauy cũ) hiểu nhầm `on` là giá trị boolean `True` (Bật/Tắt). Nếu không có ngoặc kép, cấu hình sẽ bị lỗi (Key trở thành `True` thay vì string `"on"`).
- Cú pháp: `SIGNAL: TARGET_STATE`.

### Ví dụ Thực tế

```yaml
states:
  IDLE:
    # State này chờ đợi tín hiệu từ người dùng (GUI/CLI)
    "on": 
      CMD_START: "PROCESSING"  # Nhận lệnh Start -> Chuyển sang Processing

  PROCESSING:
    # Tự động chạy chuỗi xử lý
    entry: ["p_preprocess", "p_calculate", "p_save"]
    
    # Xử lý kết quả của chuỗi
    "on":
       EVT_CHAIN_DONE: "IDLE"   # Xong -> Về IDLE
       EVT_CHAIN_FAIL: "ERROR"  # Lỗi -> Về ERROR
       CMD_CANCEL: "IDLE"       # Người dùng hủy -> Về IDLE ngay lập tức
```

---

## 2. Audit Configuration (`specs/audit_recipe.yaml`)

File này định nghĩa **Chính sách An toàn** (Safety Policy). Kernel sẽ tự động kiểm tra Input/Output của mỗi Process dựa trên recipe này trước và sau khi chạy.

### Cấu trúc

```yaml
version: "1.0"
process_recipes:
  
  process_name:
    # Kiểm tra Input (Pre-execution check)
    inputs:
      - field: "path.to.context.variable"
        type: "int" | "float" | "str" | "bool"
        min: 0
        max: 100
        regex: "^[A-Z]+$"
        required: true

    # Kiểm tra Output (Post-execution check)
    outputs:
      - field: "domain.result"
        type: "float"
```

### Các Rule phổ biến

| Rule | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `min`, `max` | int, float | Giới hạn giá trị số học. |
| `regex` | str | Kiểm tra định dạng chuỗi (VD: Email, Mã sản phẩm). |
| `enum` | str, int | Giá trị phải nằm trong danh sách cho trước (VD: `["Open", "Closed"]`). |
| `required` | any | Bắt buộc field phải tồn tại trong Context (Không được None). |

### Ví dụ: Bảo vệ Dữ liệu Tài chính

```yaml
process_recipes:
  p_transfer_money:
    inputs:
      - field: "domain_ctx.target_account"
        type: "str"
        regex: "^VN[0-9]{10}$" # Phải là tài khoản VN hợp lệ
      
      - field: "domain_ctx.amount"
        type: "float"
        min: 0.01
        max: 1000000.0 # Giới hạn chuyển 1 triệu/lần

    outputs:
      - field: "domain_ctx.transaction_status"
        enum: ["SUCCESS", "FAILED", "PENDING"]
```

---

## Tóm tắt Quy trình Phát triển

1.  **Thiết kế Logic**: Vẽ sơ đồ trạng thái (State Diagram).
2.  **Cấu hình**: Viết `workflow.yaml` dựa trên sơ đồ.
3.  **Code**: Viết các hàm `@process` tương ứng trong Python.
4.  **Bảo vệ**: Định nghĩa `audit_recipe.yaml` để ràng buộc dữ liệu.
5.  **Chạy**: `theus init` -> `python main.py`.
