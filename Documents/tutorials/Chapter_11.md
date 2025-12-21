# Chương 11: Workflow Orchestration - Từ Tuyến tính đến Phức tạp

Theus cung cấp hai chế độ điều phối: **Tuyến tính (Linear)** cho các tác vụ đơn giản và **FSM (State Machine)** cho các hệ thống phức tạp phản ứng theo sự kiện.

## 1. Chế độ Tuyến tính (The Pipeline Mode)
Nếu bạn chỉ cần chạy A -> B -> C (ví dụ: Tool xử lý số liệu, Script ETL), bạn không cần FSM.

### Cấu trúc `pipeline.yaml`
```yaml
steps:
  - "load_csv_data"
  - "clean_data"
  - "calculate_statistics"
  - "export_report"
```

### Cách chạy
Engine sẽ tự động phát hiện danh sách `steps` và chạy tuần tự.
```python
engine.execute_workflow("pipeline.yaml")
```
Nếu bất kỳ bước nào lỗi (Exception/Audit Block), toàn bộ Pipeline dừng lại (trừ khi bạn catch lỗi trong process).

## 2. Chế độ FSM (The Reactive Mode)
Khi hệ thống cần:
- Chờ đợi sự kiện (User click, Webhook).
- Rẽ nhánh (If error -> Retry, If success -> Next).
- Vòng lặp (Loop).

Lúc này bạn cần **Workflow Manager** và cấu trúc `states`.

### Cấu trúc `app.yaml`
```yaml
states:
  IDLE:
    events:
      CMD_START_WORK: "PROCESSING"  # Nghe lệnh START -> Chuyển state
      
  PROCESSING:
    entry: ["process_step_1", "process_step_2"] # Vào state -> Chạy chuỗi process này
    events:
      EVT_STEP_DONE: "VERIFYING"    # Sự kiện nội bộ tự bắn ra
      EVT_ERROR: "RECOVERY"         # Xử lý lỗi
      
  VERIFYING:
    entry: "process_verify_audit"
    events:
      EVT_AUDIT_OK: "DONE"
      EVT_AUDIT_FAIL: "RECOVERY"
      
  DONE:
    entry: "process_notify_user"
    # Kết thúc vòng lặp
```

## 3. Signal Bus & Sự kiện (Dành cho FSM)
Trong chế độ FSM, Process giao tiếp với Orchestrator qua **Signal Zone**.

```python
@process(outputs=['domain.sig_evt_step_done'])
def process_step_2(ctx):
    # Làm việc xong...
    ctx.domain.sig_evt_step_done = True # Bắn tín hiệu
```

`WorkflowManager` sẽ lắng nghe sự thay đổi trên Signal Zone. Khi thấy `sig_evt_step_done` bật lên, nó sẽ tra cứu bảng FSM và thực hiện chuyển trạng thái.

## 4. Chạy Workflow Manager (FSM)
```python
from theus.orchestrator import WorkflowManager, SignalBus

bus = SignalBus()
wm = WorkflowManager(engine, scheduler, bus)

# 1. Load YAML
wm.load_workflow(yaml_def)

# 2. Start Loop (Thường chạy trong Thread riêng hoặc Main Loop)
wm.run_workflow("MyFlow", context=None)

# 3. Kích hoạt từ bên ngoài
bus.emit("CMD_START_WORK")
```

---
**Thực hành:**
1. Tạo `linear.yaml` gồm 2 bước: `add_product` và `add_product` (thêm 2 món). Chạy thử bằng `engine.execute_workflow`.
2. Tạo `fsm.yaml` với 2 state `WAIT` và `RUN`. Dùng `WorkflowManager` để chạy thử.
So sánh sự khác biệt.
