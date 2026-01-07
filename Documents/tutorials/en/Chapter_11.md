# Chapter 11: Workflow Orchestration (FSM)

Theus v2 uses a **Finite State Machine (FSM)** to coordinate complex Agent behaviors. Instead of hardcoding `if/else` logic, you define a **Reactive Workflow** in YAML.

## 1. The Components

The orchestration layer consists of three parts:
1.  **WorkflowManager:** The Conductor. It connects the Brain (FSM) with the Hands (Engine).
2.  **SignalBus:** The Nervous System. It carries events (Signals) from processes/UI to the Manager.
3.  **ThreadExecutor:** The Scheduler. It executes process chains in background threads to keep the main loop responsive.

## 2. Defining a Workflow (YAML)

Create a `workflow.yaml` file. The structure maps **States** to **Events**.

```yaml
name: "FulfillmentWorkflow"
start_state: "IDLE"

states:
  IDLE:
    events:
      CMD_START: "PROCESSING"  # Event -> Next State

  PROCESSING:
    # Action: Run these processes immediately upon entering State
    entry: 
      - "p_validate_order"
      - "p_charge_payment"
    
    events:
      EVT_CHAIN_DONE: "SHIPPING"  # transitions after 'entry' chain success
      EVT_CHAIN_FAIL: "ERROR_RECOVERY"

  SHIPPING:
    entry: ["p_ship_item"]
    events:
      EVT_CHAIN_DONE: "IDLE"

  ERROR_RECOVERY:
    entry: ["p_alert_admin", "p_refund"]
    events:
      EVT_CHAIN_DONE: "IDLE"
```

## 3. Emitting Signals

Your processes (Python functions) drive the flow by emitting signals or simply finishing successfully.

- **Implicit Signal:** When an `entry` chain finishes, `WorkflowManager` automatically emits `EVT_CHAIN_DONE` (or `EVT_CHAIN_FAIL`).
- **Explicit Signal:** You can emit custom signals from your code or UI.

```python
# From UI / Main Loop
bus.emit("CMD_START")

# From inside a Process (if needed)
# ctx.domain.sig_custom_event = True 
# (Theus Engine automatically converts Context Signals to Bus Events if configured)
```

## 4. Running the Orchestrator

The best practice is to run the Orchestrator in a background thread so your Application (GUI/API) isn't blocked.

```python
from theus.orchestrator import WorkflowManager, SignalBus, ThreadExecutor
from theus import TheusEngine
import threading

# 1. Setup
bus = SignalBus()
scheduler = ThreadExecutor(max_workers=2)
# Engine setup (see Chapter 4) ...
manager = WorkflowManager(engine, scheduler, bus)

# 2. Load Workflow
with open("specs/workflow.yaml") as f:
    manager.load_workflow(yaml.safe_load(f))

# 3. Create a Non-Blocking Loop
def orchestrator_loop():
    while True:
        try:
            # Block for 0.1s waiting for signal
            signal = bus.get(timeout=0.1)
            manager.process_signal(signal)
        except:
            pass # Handle empty queue or exit signal

# 4. Start Thread
t = threading.Thread(target=orchestrator_loop, daemon=True)
t.start()

# 5. Interact
bus.emit("CMD_START")
```

## 5. Summary
- **Declarative:** Logic is in YAML, not Python.
- **Reactive:** System sleeps until a Signal arrives.
- **Resilient:** Failures trigger `EVT_CHAIN_FAIL`, allowing you to define `ERROR_RECOVERY` states explicitly.
