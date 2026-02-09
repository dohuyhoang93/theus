# Theus v3 API Reference

> **Quick Reference:** Concise guide to `theus` v3 public API signatures.  
> This is a standalone reference document - not part of the sequential tutorial chapters.

---

## 1. Engine (`theus.engine.TheusEngine`)

### Constructor
```python
engine = TheusEngine(
    context: Optional[BaseSystemContext] = None,
    strict_guards: bool = True,
    strict_cas: bool = False,
    audit_recipe: Optional[dict] = None
)
```
*   `context`: Initial system context.
*   `strict_guards`: Enforces Contract I/O & Policies (Default: True).
*   `strict_cas`: `True`=Strict Versioning (Zero Trust), `False`=Smart Conflict Resolution.
*   `audit_recipe`: Audit configuration (dict or YAML path).

---

### Core Methods

#### `register(func)`
Registers a `@process` decorated function.
```python
engine.register(my_process)
```

---

#### `execute(func_or_name, *args, **kwargs)` -> `Any`
Executes process synchronously or awaits async process.
*   Supports automatic retry with exponential backoff on CAS conflicts (v3.0+).
*   See Chapter 4 for execution pipeline details.

```python
result = await engine.execute("process_name", arg1=val1)
# Or with positional args:
result = await engine.execute(my_func, ctx_arg, other_arg)
```

---

#### `execute_parallel(process_name, **kwargs)` -> `Any`
Executes process in separate Interpreter/Process.
*   Requires `@process(parallel=True)`.
*   See Chapter 19 for Zero-Copy data passing.

**Environment Variables:**
*   `THEUS_USE_PROCESSES=1`: Force ProcessPool instead of InterpreterPool.
*   `THEUS_POOL_SIZE=N`: Set pool size (default: 4).

```python
result = engine.execute_parallel("cpu_intensive_task", data=large_array)
```

---

#### `edit()` (Context Manager)
Safe Zone for external mutation.
```python
with engine.edit() as ctx:
    ctx.domain.counter = 999
```
*   **Safety:** Automates serialization and syncs to Rust Core.
*   **Rollback:** Auto-rolls back state if an exception occurs.

---

#### `compare_and_swap(expected_version, data=None, heavy=None, signal=None, requester=None)` -> `None`
Atomic state update with MVCC.
*   `expected_version`: Current `engine.state.version`.
*   `requester`: Optional process name for Priority Ticket (VIP access).
*   See Chapter 22 for MVCC mechanics.

**Behavior:**
*   `strict_cas=False` (default): Smart CAS with key-level conflict detection.
*   `strict_cas=True`: Strict mode - rejects ALL version mismatches.

```python
engine.compare_and_swap(
    expected_version=engine.state.version,
    data={"domain.counter": 42},
    requester="critical_process"
)
```

---

#### `transaction(write_timeout_ms=5000)` (Context Manager)
Manual transaction logging.
```python
with engine.transaction() as tx:
    tx.update(data={"domain.value": 123})
    # Commit happens automatically on context exit
```

---

### Properties
*   `engine.state`: `RestrictedStateProxy` (Read-Only snapshot).
*   `engine.heavy`: `HeavyZoneAllocator` (Managed SharedMemory).

---

## 2. Contracts (`theus.contracts`)

### `@process` Decorator
```python
@process(
    inputs: List[str] = [],
    outputs: List[str] = [],
    semantic: SemanticType = SemanticType.EFFECT,
    errors: List[str] = [],           # Optional
    side_effects: List[str] = [],     # Optional
    parallel: bool = False
)
```
*   `inputs`: Read permissions (See Chapter 5).
*   `outputs`: Write permissions.
*   `semantic`: `PURE`, `EFFECT`, or `GUIDE`.
*   `errors`: Declared error paths.
*   `side_effects`: Declared side-effect operations.
*   `parallel`: Enable true parallelism (Sub-Interpreter or ProcessPool).

**Example:**
```python
@process(
    inputs=["domain.config"],
    outputs=["domain.result"],
    semantic=SemanticType.PURE
)
def compute(ctx):
    return ctx.domain.config * 2
```

---

## 3. Context (`theus.context`)

### `BaseSystemContext`
Root context class for user implementations.
```python
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

class MyDomain(BaseDomainContext):
    counter: int = 0
    data: list = []

class MyGlobal(BaseGlobalContext):
    config: dict = {}

class MyContext(BaseSystemContext):
    global_ctx: MyGlobal
    domain: MyDomain
```

---

### `HeavyZoneAllocator` (`engine.heavy`)
Managed SharedMemory allocator for Zero-Copy parallelism.

**Methods:**
*   `alloc(key: str, shape: Tuple, dtype: str)` -> `ShmArray`

**Example:**
```python
# Allocate shared memory for large array
arr = engine.heavy.alloc("embeddings", shape=(10000, 768), dtype="float32")
arr[:] = my_numpy_array  # Zero-copy write
```

See Chapter 10 for detailed usage.

---

## 4. Structures (`theus.structures`)

### `StateUpdate`
Explicit return type for processes to request state changes.

```python
from theus.structures import StateUpdate

StateUpdate(
    key: str = None,              # Single key update
    val: Any = None,
    data: Dict = None,            # Bulk update
    heavy: Dict = None,           # Heavy Zone updates
    signal: Dict = None,          # Signal Zone updates
    assert_version: int = None    # Expected version for CAS
)
```

**Example:**
```python
@process(outputs=["domain.counter"])
def increment(ctx):
    return StateUpdate(
        key="domain.counter",
        val=ctx.domain.counter + 1,
        assert_version=ctx.state.version
    )
```

---

## 5. CLI Tools

See Chapter 15 for full CLI reference.

**Available commands:**
```bash
# Initialize project structure
py -m theus.cli init

# Lint contracts and structure
py -m theus.cli check

# Generate audit specification
py -m theus.cli audit gen-spec
```

---

## 6. SignalHub (`theus_core.SignalHub`)

> **⚠️ Important:** SignalHub uses plain string messages, not structured events.  
> For structured data, serialize to JSON before publishing.

High-performance async broadcasting backed by Tokio.

### Constructor
```python
from theus import SignalHub

hub = SignalHub()  # No arguments
```

---

### Methods

#### `publish(msg: str)` -> `int`
Broadcast a string message to all subscribers.
*   **Returns:** Number of active receivers.

```python
# Plain string
hub.publish("sensor_reading:42.5")

# Structured data (serialize first)
import json
hub.publish(json.dumps({"topic": "sensor", "value": 42.5}))
```

---

#### `subscribe()` -> `SignalReceiver`
Create a new receiver for this hub.
*   Returns a `SignalReceiver` object.
*   Receivers get ALL messages published after subscription.

```python
rx = hub.subscribe()
```

---

### SignalReceiver

#### `recv()` -> `str`
**Blocking** receive. Waits for next message.
*   Returns a plain string.
*   Raises `RuntimeError` if channel is lagged (buffer overflow).

```python
msg = rx.recv()
print(msg)  # "sensor_reading:42.5"

# Parse structured data
data = json.loads(msg)
print(data["topic"], data["value"])
```

---

#### `recv_async()` -> `Awaitable[str]` ⭐ **Recommended** (v3.0+)
**Native async** receive. Returns Python awaitable.
*   **Non-blocking:** Can be cancelled and timed out properly.
*   **Performance:** ~13x faster than `asyncio.to_thread(recv())`.
*   Raises `RuntimeError` if channel is lagged (buffer overflow).

```python
import asyncio

async def listen(rx):
    while True:
        # Native async - clean and fast!
        msg = await rx.recv_async()
        print(f"Received: {msg}")

# With timeout
async def listen_with_timeout(rx):
    try:
        msg = await asyncio.wait_for(
            rx.recv_async(),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        print("No message within 5 seconds")

# Start listener
asyncio.create_task(listen(hub.subscribe()))
```

See **Chapter 23: SignalHub & Events** for detailed examples.

---

## 7. Design Patterns

### Outbox Pattern
Use `domain.outbox_queue` + Async Relay Loop for safe external side-effects.
*   See **Chapter 24: The Outbox Pattern** for implementation.

**Summary:**
1.  Process writes commands to `outbox_queue` instead of performing side-effects.
2.  Engine commits atomically.
3.  Background relay worker processes queue and executes side-effects.

---

### Pipeline Pattern
Use pure Python functions inside a single `@process` to avoid nested execution deadlocks.
*   See Chapter 6 for details.

---

## 8. Navigation

- [Chapter 22: Inside Theus Engine - Transaction Mechanism](./Chapter_22.md)
- [Chapter 23: SignalHub & Events](./Chapter_23_SignalHub.md)
- [Chapter 24: The Outbox Pattern](./Chapter_24_Outbox_Pattern.md)
- [Back to Tutorial Index](./README.md)

---
