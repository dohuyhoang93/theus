# Chapter 11: Workflow Orchestration (Flux DSL)

> **⚠️ MAJOR CHANGE in v3.0:** The legacy FSM (Finite State Machine) with `states:` and `events:` has been **deprecated**. Theus v3.0 uses **Flux DSL** - a declarative YAML language for workflow control.

## 1. What Changed?

| v2.2 (Deprecated) | v3.0 (Current) |
|:------------------|:---------------|
| `WorkflowManager` (Python) | `WorkflowEngine` (Rust) |
| `SignalBus` | `SignalHub` (Tokio) |
| `states:` / `events:` | `steps:` with `flux:` control flow |
| Tick-based | Run-to-Completion |

## 2. Flux DSL Syntax

### Basic Structure

```yaml
# workflows/example.yaml
steps:
  - process: "initialize"
  - process: "process_data"
  - process: "finalize"
```

### Conditional: flux: if

```yaml
steps:
  - flux: if
    condition: "domain['is_valid'] == True"
    then:
      - "handle_valid"
      - "save_result"
    else:
      - "handle_invalid"
```

### Loop: flux: while

```yaml
steps:
  - flux: while
    condition: "domain['remaining'] > 0"
    do:
      - "process_one_item"
```

### Nested Block: flux: run

```yaml
steps:
  - flux: run
    steps:
      - "step_a"
      - "step_b"
```

## 3. Complete Workflow Example

```yaml
# workflows/agent_loop.yaml
steps:
  # 1. Initialize
  - process: "p_init_agent"
  
  # 2. Main loop
  - flux: while
    condition: "domain['goal_reached'] == False and domain['step_count'] < global['max_steps']"
    do:
      # Think
      - process: "p_observe"
      - process: "p_think"
      
      # Decide
      - flux: if
        condition: "domain['confidence'] > 0.8"
        then:
          - process: "p_act"
        else:
          - process: "p_ask_for_help"
      
      # Update state
      - process: "p_update_state"
  
  # 3. Finalize
  - flux: if
    condition: "domain['goal_reached'] == True"
    then:
      - process: "p_report_success"
    else:
      - process: "p_report_failure"
```

## 4. Condition Expression Reference

| Element | Example |
|:--------|:--------|
| `domain` | `domain['items']` |
| `global` | `global['max_limit']` |
| Comparison | `==`, `!=`, `>`, `<`, `>=`, `<=` |
| Boolean | `and`, `or`, `not` |
| `len()` | `len(domain['items']) > 0` |
| `True/False/None` | Literals |

## 5. Executing Workflows

### Simple Execution

```python
from theus import TheusEngine

engine = TheusEngine(sys_ctx, strict_mode=True)
engine.scan_and_register("src/processes")

# Execute workflow
engine.execute_workflow("workflows/agent_loop.yaml")
```

### WorkflowEngine (Advanced)

```python
from theus_core import WorkflowEngine, FSMState

# Load YAML
with open("workflow.yaml") as f:
    yaml_config = f.read()

# Create engine
workflow = WorkflowEngine(
    yaml_config=yaml_config,
    max_ops=10000,  # Safety limit
    debug=False
)

# FSM States: Pending, Running, WaitingIO, Complete, Failed
print(workflow.state)  # FSMState.Pending

# Execute
ctx_dict = {"domain": sys_ctx.domain_ctx.__dict__, "global": sys_ctx.global_ctx.__dict__}
executed = workflow.execute(ctx_dict, lambda name: engine.execute(name))
```

## 6. Safety Features

### Max Operations Limit

```python
# Raises RuntimeError if exceeded
workflow = WorkflowEngine(yaml_config, max_ops=10000)
# RuntimeError: Flux Safety Trip: Exceeded 10000 operations.
```

### State Observation

```python
# Get state history
history = workflow.state_history  # [Pending, Running, Complete]

# Add observer
def on_state_change(old_state, new_state):
    print(f"State: {old_state} -> {new_state}")

workflow.add_state_observer(on_state_change)
```

## 7. Why Flux DSL?

> **🧠 Philosophy Note:** By lifting control flow out of Python code and into YAML, we achieve **"Logic-Flow Separation"**. Your Python code becomes a library of tools (Processes), and the YAML becomes the instruction manual (Workflow). This makes the system easier to visualize and modify without touching code.

**Benefits:**
- **Resilience:** State is persisted in Context. If system crashes, it recovers.
- **Performance:** The loop runs in Rust, bypassing Python GIL for control logic.
- **Visibility:** Business rules in YAML are easier to audit than nested Python.

---
**Exercise:**
Create a `workflow.yaml` with a while loop that runs until `domain['count'] >= 5`. Inside the loop, call a process that increments count. Observe the execution path.
