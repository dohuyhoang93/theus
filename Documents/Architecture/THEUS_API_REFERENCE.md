# Theus Framework v3.0.2 - API Reference

This document provides a comprehensive reference for the public APIs of the Theus Framework.

---

## 🏗️ Core API (`theus`)

The top-level package exports the essential tools for building applications.

```python
from theus import TheusEngine, process, ContractViolationError
```

### 1. Decorator: `@process`
Used to define a Theus Process. Transforms a standard function into a managed unit of work.

```python
@process(
    inputs: List[str] = [], 
    outputs: List[str] = [], 
    semantic: SemanticType = SemanticType.EFFECT, 
    errors: List[str] = [], 
    side_effects: List[str] = [], 
    parallel: bool = False
)
def my_function(ctx, *args, **kwargs): ...
```

*   **inputs**: List of context paths this process reads from (e.g., `['domain.order']`). Enforced as Read-Only.
*   **outputs**: List of context paths this process writes to. Enforced as Write-Only.
*   **semantic**: `SemanticType.PURE`, `EFFECT`, or `GUIDE`.
*   **parallel**: If `True`, runs in a separate process via `ProcessPool` (requires input args to be picklable).

---

## ⚙️ Engine API (`theus.engine`)

### Class `TheusEngine`
The central nervous system of Theus. Manages state, transactions, and execution.

#### Constructor
```python
engine = TheusEngine(
    system_context: BaseSystemContext, 
    strict_mode: bool = True
)
```
*   **strict_mode**: If `True`, enables `ContextGuard` and Linter checks. If `False`, runs in "Research Mode" (full access).

#### Methods

*   **`register(func)`**:
    Registers a `@process` function with the engine. Validates architectural constraints (e.g., Pure processes cannot read Signals).

*   **`execute(func_or_name, *args, **kwargs) -> Any`**:
    Executes a process transactionally.
    *   **Atomic:** All or nothing commitment of state changes.
    *   **Safety:** Handles CAS Conflicts with Automatic Backoff & VIP Locking.
    *   **Async:** Can be awaited (`await engine.execute(...)`).

*   **`execute_workflow(yaml_path: str)`**:
    Runs an orchestration workflow defined in Flux DSL YAML.
    **Note (v3.0.2+):** Flux workflows now have full access to `signal` and `cmd` zones for event-driven logic.
    ```yaml
    - flux: if
      condition: "signal.get('cmd_stop') == 'True'"
      then: ...
    ```

*   **`scan_and_register(path: str)`**:
    **Auto Discovery.** Recursively scans the given directory path for Python files, imports them, and automatically registers any functions decorated with `@process`.

---

## 🔒 Audit API (`theus.audit`)

System for enforcing runtime behavior policies (e.g., stopping a process after too many failures).

```python
from theus.audit import AuditSystem, AuditRecipe

# 1. Define Rules
recipe = AuditRecipe(
    threshold_max=5,       # Max failures allowed
    reset_on_success=True  # Clear counter on success
)

# 2. Attach to Engine
engine = TheusEngine(..., audit_recipe=recipe)
```

*   **`AuditBlockError`**: Raised if a process is blocked by the audit system.

---

## 💾 Managed Memory API (`SharedMemory`)

Advanced API for Zero-Copy tensor sharing. 
**Note:** Allocation must be done by the **Orchestrator/Main** thread via `engine.heavy`. Processes only consume (read/write) the allocated buffers via `ctx.heavy`.

```python
# 1. Main Thread: Allocate
def main():
    engine = TheusEngine(...)
    
    # Alloc: Create 2GB tensor in shared memory
    array = engine.heavy.alloc(
        key="my_tensor", 
        shape=(10000, 10000), 
        dtype="float32"
    )
    
    # Commit handle to State
    engine.compare_and_swap(
        engine.state.version, 
        heavy={"global_tensor": array}
    )

# 2. Process: Use
@process(inputs=['heavy.global_tensor'])
def process_data(ctx):
    # Zero-Copy Access
    arr = ctx.heavy['global_tensor'] 
    arr[0,0] = 1.0  # Direct mutation of memory is allowed (if logic requires)
    return None
```

*   **`engine.heavy.alloc(...)`**: Allocates a new shared memory segment.
*   **`ctx.heavy[...]`**: Access existing shared memory segments as Numpy-like arrays.

---

## 🗃️ Context API (`theus.context`)

Base classes for defining your application structure.

### 🛡️ Immutable Context & Updates
Theus contexts are **Read-Only** by default. You cannot do `ctx.domain.x = 1`.
To update state, you should use the **POP Contract Pattern**:

1.  **Implicit Return (Recommended):**
    Declare `outputs` in the decorator and return the new values.
    ```python
    @process(inputs=['domain.count'], outputs=['domain.count'])
    def increment(ctx):
        return ctx.domain.count + 1
    ```

2.  **Explicit `StateUpdate` (Advanced):**
    Used when you need precise control over CAS versions or need to update multiple zones at once.
    ```python
    from theus.structures import StateUpdate
    
    return StateUpdate(
        data={"domain": {"x": 1}},
        heavy={"tensor": my_array}
    )
    ```

### Class `BaseSystemContext`
The root container.
```python
@dataclass
class MyContext(BaseSystemContext):
    global_ctx: MyGlobal
    domain_ctx: MyDomain
```

### Class `BaseDomainContext` / `BaseGlobalContext`
Inherit from `LockedContextMixin` to enforce architectural access logic.

---

## 🔨 CLI Tools (`theus.cli`)

Command line interface for managing projects.
Usage: `python -m theus.cli <command> <subcommand>`

| Command | Subcommand | Arguments | Description |
| :--- | :--- | :--- | :--- |
| **init** | | `name`, `--template` | Create new project. (`python -m theus.cli init ...`) |
| **check** | | `path`, `--format` | Run POP Linter (Static Analysis). |
| **audit** | `gen-spec` | | Generate `audit_recipe.yaml` from code. |
| **audit** | `inspect` | `process_name` | View effective rules for a process. |
| **schema** | `gen` | `--context-file` | Generate YAML Schema from Python dataclasses. |
| **schema** | `code` | `--schema-file` | Generate Python code from YAML Schema. |

---

## 🧩 Structures (`theus.structures`)

Low-level data structures used for state management.

*   **`State`**: The Rust-managed state container.
*   **`FrozenDict`**: Immutable dictionary used for Read-Only views.
*   **`StateUpdate`**: Explicit return type for specialized commits (Context + Heavy + Signal).

---

## 📡 Signal API (`theus_core.signals`)

Theus v3 features a high-performance, asynchronous signaling system powered by **Tokio Events** (Rust). Signals are ephemeral broadcast messages used for inter-process communication and control flow.

### 1. Structure
*   **Topic**: String identifier (e.g., `cmd_stop`, `sig_alert`).
*   **Payload**: String message (JSON or text).
*   **Behavior**: Broadcast to all subscribers. Forgotten after 1 Tick (Ephemeral).

### 2. Sending Signals (`StateUpdate`)
The recommended way to send signals from a process is via the `StateUpdate` return object.

```python
from theus.structures import StateUpdate

@process(outputs=['signal.cmd_stop'])
def trigger_emergency(ctx):
    # Sends 'cmd_stop' with payload "True"
    return StateUpdate(
        signal={'cmd_stop': True}
    )
```

### 3. Receiving Signals (Low-Level)
Advanced users can subscribe to the raw signal stream using the `SignalHub` exposed on the state.

```python
# Access Hub (Rust Object)
hub = engine.state.signal      # Returns SignalHub

# Subscribe
receiver = hub.subscribe()     # Returns SignalReceiver

# Blocking Receive (Releases GIL)
# Best used in separate threads or async tasks
try:
    msg = receiver.recv()      # "topic:payload"
    print(f"Got signal: {msg}")
except StopAsyncIteration:
    print("Channel Closed")
```

### 4. Flux Control Signals
In Flux Workflows, signals are automatically captured ("latched") at the start of each step for evaluation.

**Accessing Signals in YAML:**
Use the `signal` dictionary (or `cmd` alias). Since signals are ephemeral, always use `.get()` to avoid errors if the signal is absent.

```yaml
steps:
  - flux: if
    # Check if 'cmd_emergency' signal was sent this tick
    condition: "signal.get('cmd_emergency') == 'True'"
    then:
      - process: p_shutdown_system
```

**Common Patterns:**
*   `cmd_*`: Command directives (e.g., `cmd_start`, `cmd_stop`). Force an action.
*   `sig_*`: Notification events (e.g., `sig_user_login`). Informational.

---

## 🧱 Zones (`theus.zones`)

*   **`ContextZone`**: Enum (`DATA`, `SIGNAL`, `META`, `HEAVY`).
*   **`resolve_zone(key)`**: Helper to determine zone from variable prefix.

---

*Generated for Theus v3.0.2*
