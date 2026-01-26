# Module 04: Workflow and Flux DSL

> **For AI Assistants:** Flux DSL is the YAML-based workflow language. This replaced the legacy Python FSM in v3.0.

---

## 1. Flux DSL Overview

Flux DSL is a declarative language for defining agent workflows in YAML.

### Key Concepts

| Concept | Description |
|:--------|:------------|
| **Steps** | List of operations to execute |
| **Process** | Call a registered @process function |
| **Flux: if** | Conditional branching |
| **Flux: while** | Loop while condition is true |
| **Flux: run** | Nested block of steps |

---

## 2. Basic Workflow Structure

```yaml
# workflows/example_workflow.yaml

# Simple linear workflow
steps:
  - process: "initialize"
  - process: "process_data"
  - process: "finalize"
```

### Execute from Python

```python
engine.execute_workflow("workflows/example_workflow.yaml")
```

---

## 3. Flux DSL Syntax

### Process Step

```yaml
steps:
  # Shorthand (string)
  - "process_name"
  
  # Explicit (mapping)
  - process: "process_name"
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

**Condition Syntax:**
- Access context via `domain`, `global` dicts
- Standard Python operators: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Boolean: `and`, `or`, `not`
- Boolean: `and`, `or`, `not`
- Functions: `len()`, `int()`, `str()`, `bool()`, `abs()`, `min()`, `max()`, `sum()`
- Signals: `signal.get('key')` (Returns None if not present)

### Loop: flux: while

```yaml
steps:
  - flux: while
    condition: "domain['remaining'] > 0"
    do:
      - "process_one_item"
```

**Safety:** Engine has `max_ops` limit (default 10000) to prevent infinite loops.

### Nested Block: flux: run

```yaml
steps:
  - flux: run
    steps:
      - "step_a"
      - "step_b"
      - flux: if
        condition: "domain['x'] > 0"
        then:
          - "step_c"
```

---

## 4. Complete Workflow Example

```yaml
# workflows/agent_loop.yaml
# Agent deliberation loop with error handling

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

---

## 5. WorkflowEngine (Rust)

The `WorkflowEngine` is the Rust-powered executor for Flux DSL.

### Initialization

```python
from theus_core import WorkflowEngine

# Load YAML config
with open("workflow.yaml") as f:
    yaml_config = f.read()

# Create engine
workflow = WorkflowEngine(
    yaml_config=yaml_config,
    max_ops=10000,  # Safety limit
    debug=False
)
```

### FSM States

```python
from theus_core import FSMState

class FSMState:
    Pending = 0    # Initial state
    Running = 1    # Executing steps
    WaitingIO = 2  # Waiting for async I/O
    Complete = 3   # Successfully finished
    Failed = 4     # Error occurred
```

### Execute Methods

```python
# Synchronous execution
executed_processes = workflow.execute(ctx_dict, executor_callback)

# Asynchronous execution (for async processes)
executed_processes = await workflow.execute_async(ctx_dict, executor_callback)
```

### State Observation

```python
# Get current state
state = workflow.state  # or workflow.fsm_state

# Get state history
history = workflow.state_history  # [Pending, Running, Complete]

# Add observer
def on_state_change(old_state, new_state):
    print(f"State: {old_state} -> {new_state}")

workflow.add_state_observer(on_state_change)
```

---

## 6. Integration with TheusEngine

The simplest way to execute workflows:

```python
from theus import TheusEngine

engine = TheusEngine(sys_ctx, strict_mode=True)

# Register all processes
engine.scan_and_register("src/processes")

# Execute workflow
engine.execute_workflow("workflows/main.yaml")
```

Internally, `execute_workflow`:
1. Loads YAML from file
2. Creates `WorkflowEngine`
3. Provides an executor that calls `engine._run_process_sync()`
4. Executes steps

---

## 7. Condition Expression Reference

### Available in Conditions

| Element | Example |
|:--------|:--------|
| `domain` | `domain['items']` |
| `global` | `global['max_limit']` |
| `signal` | `signal.get('cmd_start')` |
| Comparison | `==`, `!=`, `>`, `<`, `>=`, `<=` |
| Boolean | `and`, `or`, `not` |
| `len()` | `len(domain['items']) > 0` |
| `int/float/str/bool` | Type casting |
| `abs/min/max/sum` | Math functions |
| `True/False/None` | Literals |

### Examples

```yaml
# Simple comparison
condition: "domain['count'] > 10"

# Boolean logic
condition: "domain['is_ready'] and not domain['is_paused']"

# List operations
condition: "len(domain['queue']) > 0"

# Complex
condition: "domain['score'] >= global['threshold'] and domain['attempts'] < 3"
```

---

## 8. Error Handling in Workflows

### Safety Trip

If loop exceeds `max_ops`:

```python
# Raises:
# RuntimeError: Flux Safety Trip: Exceeded 10000 operations. 
# Check for infinite loops.
```

### Process Failure

If a process raises an exception:
1. Workflow transitions to `Failed` state
2. Exception propagates to caller
3. Context changes are rolled back (if strict_mode)

### Handling Pattern

```python
try:
    engine.execute_workflow("workflow.yaml")
except RuntimeError as e:
    if "Safety Trip" in str(e):
        print("Infinite loop detected")
    else:
        print(f"Workflow error: {e}")
except Exception as e:
    print(f"Process error: {e}")
```

---

## 9. Deprecated: Legacy FSM

> **AI Warning:** The following are DEPRECATED in v3.0:
> - `WorkflowManager` class
> - `SignalBus` class
> - `ThreadExecutor` class
> - `states:` / `events:` YAML syntax

**Old v2 syntax (DO NOT USE):**
```yaml
# ❌ DEPRECATED
states:
  IDLE:
    events:
      CMD_START: "PROCESSING"
```

**New v3 syntax:**
```yaml
# ✅ CURRENT
steps:
  - process: "start_processing"
```

---

## 10. AI Implementation Checklist

When generating Flux DSL workflows:

- [ ] Use `steps:` as root key
- [ ] Use `- process: "name"` for process calls
- [ ] Use `flux: if` with `condition`, `then`, `else`
- [ ] Use `flux: while` with `condition`, `do`
- [ ] Access context via `domain['key']` not `domain.key`
- [ ] Keep conditions simple (no function calls except builtins)
- [ ] Set reasonable `max_ops` for loops
- [ ] Handle workflow errors in Python caller

---

*Next: [05_AUDIT_SYSTEM.md](./05_AUDIT_SYSTEM.md)*
