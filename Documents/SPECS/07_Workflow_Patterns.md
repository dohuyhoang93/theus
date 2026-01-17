# Chương 7: Mô hình Workflow & Ngôn ngữ Flux DSL

> **⚠️ THAY ĐỔI LỚN v3.0:** FSM (states/events) đã được **DEPRECATED**. Theus v3.0 sử dụng **Flux DSL** làm engine chính cho workflow.

Theus v3.0 hỗ trợ hai mô hình điều phối (Orchestration Patterns):

1.  **The Pipeline (Flux DSL):** Workflow chính sử dụng if/while/run trong YAML.
2.  **SignalHub:** Event system cho các ứng dụng reactive (thay thế SignalBus cũ).

---

## 7.1. Pattern 1: The Pipeline (Flux DSL)

Đây là mô hình mặc định và **được khuyến nghị** trong v3.0. Bạn định nghĩa một chuỗi các bước (Steps) để Engine thực thi.

### Cấu trúc `workflow.yaml`
```yaml
# Linear Control Flow với Flux DSL
steps:
  - process: "etl.extract_data"
  
  - flux: if
    condition: "domain['has_new_data'] == True"
    then:
      - "etl.transform"
      - "etl.load"
    else:
      - "etl.skip_with_log"
      
  - flux: while
    condition: "domain['items_remaining'] > 0"
    do:
      - "etl.process_next_item"
```

### Các từ khóa Flux DSL

| Từ khóa | Mô tả | Ví dụ |
|:--------|:------|:------|
| `process:` | Gọi một process | `- process: "my_func"` |
| `flux: if` | Rẽ nhánh | `condition`, `then`, `else` |
| `flux: while` | Vòng lặp | `condition`, `do` |
| `flux: run` | Nhóm bước lồng nhau | `steps` |

### Condition Syntax

Conditions sử dụng dict access:
```yaml
# Truy cập domain context
condition: "domain['is_valid'] == True"

# Truy cập global context
condition: "global['max_steps'] > domain['current_step']"

# Boolean operators
condition: "domain['ready'] and not domain['paused']"

# Functions
condition: "len(domain['items']) > 0"
```

> **Khi nào dùng:** Mọi workflow - từ simple scripts đến complex agent loops.

---

## 7.2. Pattern 2: SignalHub (Event-Driven)

Với các ứng dụng cần **real-time events** như GUI hoặc multi-agent systems, Theus v3.0 cung cấp **SignalHub** (backed by Tokio).

### SignalHub vs SignalBus (Legacy)

| Đặc điểm | SignalBus (v2.2) | SignalHub (v3.0) |
|:---------|:-----------------|:-----------------|
| Backend | Python Queue | **Tokio broadcast** |
| Throughput | ~10K evt/s | **2.7M+ evt/s** |
| Threading | Python threads | **Rust async** |

### Sử dụng SignalHub

```python
from theus_core import SignalHub, SignalReceiver

# Tạo hub
hub = SignalHub(capacity=1000)

# Tạo receiver (subscriber)
receiver: SignalReceiver = hub.subscribe()

# Gửi event
hub.send("CMD_START", {"data": "value"})

# Nhận event (blocking)
event = receiver.recv()

# Nhận event (async)
event = await receiver.recv_async()
```

---

## 7.3. So sánh Patterns

| Đặc điểm | Flux DSL (Pipeline) | SignalHub (Events) |
|:---------|:--------------------|:-------------------|
| **Tư duy** | Tuần tự (Steps) | Reactive (Events) |
| **Điều khiển** | `if`, `while`, `run` | `send()`, `recv()` |
| **Engine** | `WorkflowEngine` (Rust) | `SignalHub` (Tokio) |
| **Use Case** | Agent loops, Pipelines | GUI, Multi-agent comm |

---

## 7.4. Thực thi Workflow

### Cách 1: Qua TheusEngine (Đơn giản)

```python
from theus import TheusEngine

engine = TheusEngine(sys_ctx, strict_mode=True)
engine.scan_and_register("src/processes")

# Thực thi workflow
engine.execute_workflow("workflows/main.yaml")
```

### Cách 2: Qua WorkflowEngine (Chi tiết)

```python
from theus_core import WorkflowEngine, FSMState

# Load YAML
with open("workflow.yaml") as f:
    yaml_config = f.read()

# Tạo engine với safety limit
workflow = WorkflowEngine(
    yaml_config=yaml_config,
    max_ops=10000,  # Prevent infinite loops
    debug=False
)

# Executor callback
def execute_process(name):
    return engine.execute(name)

# Thực thi
ctx_dict = {
    "domain": sys_ctx.domain_ctx.__dict__,
    "global": sys_ctx.global_ctx.__dict__
}
executed = workflow.execute(ctx_dict, execute_process)

# Kiểm tra trạng thái
print(workflow.state)  # FSMState.Complete
```

---

## 7.5. FSM States (Trạng thái WorkflowEngine)

| State | Mô tả |
|:------|:------|
| `Pending` | Chưa bắt đầu |
| `Running` | Đang thực thi steps |
| `WaitingIO` | Đang chờ async I/O |
| `Complete` | Hoàn thành thành công |
| `Failed` | Gặp lỗi |

---

## 7.6. Kết luận

Trong v3.0, **Flux DSL là cách chính để viết workflows**. Bạn có thể:
*   Dùng **Flux DSL** để định nghĩa agent reasoning loops.
*   Dùng **SignalHub** để giao tiếp giữa các agents hoặc với GUI.

Sự tách biệt này giúp kiến trúc Theus vừa linh hoạt cho scripting, vừa mạnh mẽ cho application dev.
