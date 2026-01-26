# AI CODING REFERENCE: Theus FFI & Architecture

> **CRITICAL INSTRUCTION FOR AI AGENTS**:
> When writing Python code using Theus Framework, you MUST adhere to the constraints imposed by the Rust-Python FFI boundary. Code that works in standard Python may fail in Theus due to `SupervisorProxy` wrappers and Pickle limitations.

---

## 1. Handling Context Objects (SupervisorProxy)

**Context**: `ctx.domain`, `ctx.global`, and their nested fields are wrapped in a Rust `SupervisorProxy` to track mutations for MVCC Transactions.

### ⛔ NEVER DO THIS
```python
# Fails: Proxy is not a dict subclass
if isinstance(ctx.domain.order, dict): ...

# Fails: Pydantic models in Theus State lose standard serialization methods via Proxy
data = ctx.domain.my_model.model_dump() 
```

### ✅ ALWAYS DO THIS
```python
# 1. Use Duck Typing
if hasattr(ctx.domain.order, "get"): ...

# 2. Use to_dict() Helper (Built into Proxy)
order_data = ctx.domain.order.to_dict()
if isinstance(order_data, dict): ...

# 3. For Pydantic Models in State
# You MUST implement a .to_dict() method on your Pydantic classes
class MyModel(BaseModel):
    def to_dict(self):
        return self.model_dump()
```

---

## 2. Parallel Processing (Shared Memory)

**Context**: The Default `ctx.heavy` object (FrozenDict) cannot be pickled and sent to other processes.

### ⛔ NEVER DO THIS
```python
# Fails: Cannot pickle Rust Core objects
engine.execute_parallel(worker_func, data=ctx.heavy)
```

### ✅ ALWAYS DO THIS (The Metadata Pattern)
Pass only the **Handle/Name** of the shared memory resource.

**Main Process:**
```python
# Extract metadata
shm_name = ctx.heavy.input_buffer._shm_ref.name
shape = ctx.heavy.input_buffer.shape
dtype = str(ctx.heavy.input_buffer.dtype)

engine.execute_parallel("worker", 
    shm_name=shm_name, 
    shape=shape, 
    dtype=dtype
)
```

**Worker Process:**
```python
from multiprocessing.shared_memory import SharedMemory
import numpy as np

def worker(ctx):
    # Re-attach Zero-Copy
    shm = SharedMemory(name=ctx.input['shm_name'], create=False)
    arr = np.ndarray(ctx.input['shape'], dtype=ctx.input['dtype'], buffer=shm.buf)
    
    # Work on arr...
    
    shm.close() # Always close handle
```

---

## 3. Transaction Mechanics (Concept)

Understanding this helps you debug "why didn't my state update?".

*   **Mechanism**: Clone-on-Access (Shadow Copy).
*   **Behavior**: When you first write to `ctx.domain.x`, Theus DEEP COPIES the object `x` into a private shadow.
*   **Implication**:
    *   **Isolation**: You can modify freely; other processes won't see changes until you finish.
    *   **Rollback**: If you raise an Exception, the Shadow Copy is discarded. State remains untouched.
    *   **Concurrency**: Multiple processes can READ the same state version simultaneously. Writes create new versions (MVCC).

---

## 4. Scaffold Best Practices

When creating new projects (`theus init`):

1.  **Naming Alignment**: Ensure `src/context.py` field names match `BaseSystemContext`.
    *   Correct: `self.domain = MyDomain()`
    *   Incorrect: `self.domain_ctx = MyDomain()`
2.  **Serialization**: Always add `to_dict` to your `BaseModel` classes in `context.py`.

---

## 5. Conflict Resolution

If a process fails with `CAS Version Mismatch`, it means another process updated the state concurrently.
*   **Auto-Retry**: Theus `engine.execute` has built-in backoff for this.
*   **Conflict Logic**: Theus v3.3 uses "Smart CAS" - it only rejects if the *specific keys* you read/wrote were modified. Unrelated updates are merged automatically.
