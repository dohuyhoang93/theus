# Chapter 11: Workflow Manager & FSM - The Conductor v2

Theus v2 does not just run isolated processes. It uses a **Finite State Machine (FSM)** to orchestrate complex workflows reacting to events.

## 1. Workflow Manager (WM)
This is the highest-level shell of Theus.
- **Engine:** Hands (Execute Process).
- **SignalBus:** Ears (Listen to Events).
- **FSM:** Brain (Decide where to go next).

## 2. Linear Mode vs FSM Mode
Theus supports two orchestration modes.

### Linear (Pipeline)
Simple sequence A -> B -> C. No state logic needed.
```yaml
steps:
  - "load_data"
  - "process_data"
```

### FSM (Reactive)
Complex logic with states, loops, and event listeners.
```yaml
states:
  IDLE:
    events:
      CMD_START_WORK: "PROCESSING"  # Hear START command -> Switch state
      
  PROCESSING:
    entry: ["process_step_1", "process_step_2"] # Enter state -> Run these processes
    events:
      EVT_STEP_DONE: "VERIFYING"    # Internal event emitted by process
      EVT_ERROR: "RECOVERY"         # Error handling path
      
  VERIFYING:
    entry: "process_verify_audit"
    events:
      EVT_AUDIT_OK: "DONE"
      EVT_AUDIT_FAIL: "RECOVERY"
      
  DONE:
    entry: "process_notify_user"
```

## 3. Signal Bus & Events
How to emit `EVT_STEP_DONE`?
Your Process does it via the **Signal Zone**.

```python
@process(outputs=['domain.sig_evt_step_done'])
def process_step_2(ctx):
    # Work done...
    ctx.domain.sig_evt_step_done = True # Emit Signal
```

`WorkflowManager` listens to changes in Signal Zone. When `sig_evt_step_done` flips to True, it consults the FSM table and executes state transition.

## 4. Running Workflow Manager
```python
from theus.orchestrator import WorkflowManager, SignalBus

bus = SignalBus()
wm = WorkflowManager(engine, scheduler, bus)

# 1. Load YAML
wm.load_workflow(yaml_def)

# 2. Start Loop (Usually in separate Thread or Main Loop)
wm.run_workflow("MyFlow", context=None)

# 3. Trigger externally
bus.emit("CMD_START_WORK")
```

---
**Exercise:**
Create `workflow.yaml` with 2 states: `WAIT` and `RUN`.
Create a process `trigger_run` to emit signal switching to `RUN`.
Use `WorkflowManager` to run and observe state transition logs.
