# Chương 7: Mô hình Workflow & Ngôn ngữ Spec

Theus hỗ trợ hai mô hình điều phối (Orchestration Patterns) riêng biệt, phục vụ hai mục đích khác nhau:

1.  **The Pipeline (Flux Engine):** Dùng cho các tác vụ tuần tự, xử lý dữ liệu, mô phỏng (Batch Processing).
2.  **The Machine (Native FSM):** Dùng cho các ứng dụng phản ứng sự kiện, GUI, Long-running Services (Event-Driven).

---

## 7.1. Pattern 1: The Pipeline (Flux Engine)

Đây là mô hình mặc định. Bạn định nghĩa một chuỗi các bước (Steps) để Engine thực thi từ trên xuống dưới.

### Cấu trúc `workflow.yaml`
```yaml
# Linear Control Flow
steps:
  - "etl.extract_data"
  - flux: if
    condition: "domain.has_new_data"
    then:
      - "etl.transform"
      - "etl.load"
```

### Các từ khóa Flux
*   `flux: if` (Rẽ nhánh)
*   `flux: while` (Vòng lặp)
*   `flux: run` (Nhóm bước)

> **Khi nào dùng:** Khi bạn muốn máy tính "làm xong việc A rồi đến việc B".

---

## 7.2. Pattern 2: The Machine (Native FSM)

Với các ứng dụng phức tạp như GUI hoặc Robot, luồng xử lý không phải là tuyến tính mà là **Phản ứng (Reactive)**. Theus cung cấp một **Finite State Machine (FSM)** tích hợp sẵn trong module `theus.orchestrator`.

### Cấu trúc `fsm.yaml` (Khác với workflow.yaml)

```yaml
# State-Event Control Flow
initial_state: "IDLE"

states:
  IDLE:
    # Khi vào trạng thái này, chạy process gì?
    entry: "ui.show_ready" 
    
    # Lắng nghe sự kiện (Event) để chuyển trạng thái
    events:
      CMD_START: "RUNNING"
      CMD_CONFIG: "CONFIGURING"

  RUNNING:
    entry: "core.start_simulation"
    events:
      EVT_DONE: "IDLE"
      EVT_ERROR: "ERROR_STATE"

  ERROR_STATE:
    entry: "ui.show_error"
    events:
      CMD_RESET: "IDLE"
```

### Cơ chế hoạt động (The Manager Loop)
Để chạy mô hình này, bạn không dùng `engine.execute_workflow` mà dùng `WorkflowManager`:

```python
# Setup
bus = SignalBus()
manager = WorkflowManager(engine, scheduler, bus)
manager.load_workflow(fsm_def)

# Runtime
bus.emit("CMD_START") # Gửi sự kiện vào Bus
manager.run_workflow() # Manager sẽ điều phối: IDLE -> RUNNING
```

> **Khi nào dùng:** Khi hệ thống cần "chờ lệnh" hoặc xử lý bất đồng bộ (Async Events).

---

## 7.3. So sánh Flux vs FSM

| Đặc điểm | Flux (Pipeline) | FSM (Machine) |
| :--- | :--- | :--- |
| **Tư duy** | Tuần tự (Imperative) | Sự kiện (Reactive) |
| **Logic chính** | Step 1 -> Step 2 | State A + Event -> State B |
| **Điều khiển** | `if`, `while` | `transitions`, `events` |
| **Engine** | `TheusEngine` (Single Thread) | `WorkflowManager` (Multi-Thread/Worker) |
| **Use Case** | Data Pipeline, Script, Simulation Loop | App GUI, Game Loop, Server |

---

## 7.4. Kết luận

Bạn có thể kết hợp cả hai:
*   Dùng **FSM** để quản lý trạng thái cao cấp của ứng dụng (VD: App đang ở màn hình Login hay màn hình Dashboard).
*   Dùng **Flux** bên trong mỗi trạng thái để thực thi logic nghiệp vụ (VD: Khi bấm nút Login, chạy chuỗi verify mật khẩu).

Sự tách biệt này giúp kiến trúc Theus vừa linh hoạt cho scripting, vừa mạnh mẽ cho application dev.
