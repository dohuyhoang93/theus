# Chapter 23: Theus v3 Standard API Reference

> **API Cheatsheet:** Concise reference for `theus` v3 public signatures.

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
*   `strict_cas`: `True`=Strict Versioning (Zero Trust), `False`=Smart Conflict Resolution (Available).

### Core Methods

#### `register(func)`
Registers a `@process` decorated function.
```python
engine.register(my_process)
```

#### `execute(func_or_name, **kwargs)` -> `Any`
Executes process synchronously or awaits async process.
*   See Chapter 4 for execution pipeline details.
```python
result = await engine.execute("process_name", arg1=val1)
```

#### `execute_parallel(process_name, **kwargs)` -> `Any`
Executes process in separate Interpreter/Process.
*   Requires `@process(parallel=True)`.
*   See Chapter 19 for Zero-Copy data passing.

#### `edit()` (Context Manager)
Safe Zone for external mutation.
```python
with engine.edit() as ctx:
    ctx.domain.counter = 999
```
*   **Safety:** Automates serialization and provides `SupervisorProxy`.
*   **Rollback:** Auto-rolls back state if an exception occurs.

#### `compare_and_swap(expected_version, data=None, heavy=None, signal=None)`
Atomic state update.
*   `expected_version`: Current `engine.state.version`.
*   See Chapter 6 for MVCC mechanics.

#### `transaction()` (Context Manager)
Manual transaction logging.
```python
with engine.transaction() as tx:
    tx.update(data={...})
```

### Properties
*   `engine.state`: `RestrictedStateProxy` (Read-Only).
*   `engine.heavy`: `HeavyZoneAllocator`.

---

## 2. Contracts (`theus.contracts`)

### `@process` Decorator
```python
@process(
    inputs: List[str] = [],
    outputs: List[str] = [],
    semantic: SemanticType = SemanticType.EFFECT,
    parallel: bool = False
)
```
*   `inputs`: Read permissions (See Chapter 5).
*   `outputs`: Write permissions.
*   `parallel`: Enable true parallelism.

---

## 3. Context (`theus.context`)

### `BaseSystemContext`
Root context class.
```python
class MyContext(BaseSystemContext):
    global_ctx: Any
    domain: Any
```

### `HeavyZoneAllocator` (`engine.heavy`)
*   `alloc(key: str, shape: Tuple, dtype: str)` -> `ShmArray`
*   See Chapter 10 for Zero-Copy usage.

---

## 4. Structures (`theus.structures`)

### `StateUpdate`
Explicit return type for processes.
```python
StateUpdate(
    key: str = None,           # Single key update
    val: Any = None,
    data: Dict = None,         # Bulk update
    assert_version: int = None
)
```

---

## 5. CLI Tools
See Chapter 15 for full CLI reference.
*   `py -m theus.cli init`
*   `py -m theus.cli check`
*   `py -m theus.cli audit gen-spec`

---

## 6. SignalHub (`theus_core.SignalHub`)
High-performance async broadcasting.
*   **Constructor:** `SignalHub()` (No arguments).
*   **Methods:**
    *   `publish(topic: str, data: Any)`: Broadcast event.
    *   `subscribe()` -> `SignalReceiver`: Subscribe to all events.

### SignalReceiver
*   `recv()`: Blocking receive.
*   `recv_async()`: Awaitable receive.

---

## 7. Design Patterns
*   **Outbox Pattern:** Use `domain.outbox_queue` + Async Relay Loop (See Chapter 25).
*   **Pipeline Pattern:** Use pure Python functions inside a single `@process` to avoid nested execution deadlocks (See Chapter 6).

---

## 8. Navigation
- [Chapter 24: SignalHub & Events](./Chapter_24_SignalHub.md)
- [Chapter 25: The Outbox Pattern](./Chapter_25_Outbox_Pattern.md)
