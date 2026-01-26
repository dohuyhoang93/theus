# Chapter 21: Theus FFI vs. Python Idioms - A Developer's Guide

Theus v3 bridges the gap between high-performance Rust Core and dynamic Python logic. While we strive for seamless integration, the FFI (Foreign Function Interface) boundary introduces some "un-idiomatic" behaviors that developers must be aware of.

This chapter documents these "Quirks" and provides standard workarounds.

## 1. The Proxy Problem (`isinstance` failure)

### Issue
When you access `ctx.domain` or other state objects in a Process, Theus returns a `SupervisorProxy`. This proxy behaves *almost* like a dict or object (Duck Typing), but it is **NOT** a subclass of `dict`.

```python
# process.py
req = ctx.domain.order_request

# ❌ FAIL: Proxy is a Rust PyAny wrapper, not a python dict
if isinstance(req, dict): 
    ...
```

### Explanation
The `SupervisorProxy` is a Rust struct (PyClass) that wraps a pointer to the Python object. It intercepts access to log deltas for Transactions. Inheriting from Python built-in `dict` in PyO3/Rust is technically complex and has performance penalties.

### Solution: Duck Typing or Conversion
Use Duck Typing (check for behavior, not type) or convert explicitly when needed.

**Option A: Duck Typing (Recommended)**
```python
if hasattr(req, "get"): # It behaves like a dict
    val = req.get("key")
```

**Option B: Explicit Conversion (Safe)**
```python
# SupervisorProxy v3.1+ has a helper
req_dict = req.to_dict() 
if isinstance(req_dict, dict): # ✅ PASS
    ...
```

## 2. Pydantic Serialization

### Issue
Theus Engine uses `.to_dict()` protocol to serialize objects when transferring state updates to Rust. Standard Pydantic `BaseModel` uses `.model_dump()`, causing `AttributeError: object has no attribute 'to_dict'`.

### Solution: Wrapper Mixin
Add a `to_dict` method to your Pydantic models.

```python
class MyDomain(BaseModel):
    checkpoints: list = []

    # ✅ Add this adapter
    def to_dict(self):
        return self.model_dump()
```

## 3. Pickling & Parallel Processing

### Issue
Theus Core objects (like `FrozenDict` or heavily optimized Rust structs) often cannot be pickled by Python's `multiprocessing` default pickler because they do not implement `__reduce__` in a way compatible with cross-process reconstruction (they wrap local pointers).

```python
# ❌ FAIL: Passing ctx.heavy (FrozenDict) directly to worker
engine.execute_parallel(worker_func, data=ctx.heavy)
```

### Solution: Metadata Passing (Chapter 19 Pattern)
Do not pass the "Container" object. Pass the "Handle/Metadata" used to reconstruct it.

**Correct Pattern:**
1.  **Main Process:** Extract shared memory name/metadata.
    ```python
    shm_name = ctx.heavy.input_array._shm_ref.name
    engine.execute_parallel("worker", shm_name=shm_name, ...)
    ```
2.  **Worker Process:** Reconstruct the object from metadata.
    ```python
    from multiprocessing.shared_memory import SharedMemory
    
    def worker(ctx):
        name = ctx.input.get('shm_name')
        # Re-attach (Zero-Copy)
        shm = SharedMemory(name=name, create=False)
        ...
    ```

## 4. Mutable Default Arguments in Context

### Issue
In `scaffold/src/context.py`, we saw:
`self.domain_ctx = DemoDomain()`
vs
`self.domain = DemoDomain()`

### Explanation
Theus relies on strict field naming to map Python context fields to Rust State slots (`data` map). If names mismatch, data is lost (goes to `global` or ignored), causing `NoneType` errors in processes.

### Rule
Always align your Python Context class fields with the structure expected by `BaseSystemContext` (domain, global).

---

## Summary Checklist

| Idiom | Theus Reality | Workaround |
|-------|---------------|------------|
| `isinstance(x, dict)` | `False` (It is a Proxy) | Use `hasattr(x, 'get')` or `x.to_dict()` |
| `pickle.dumps(obj)` | Fails for Rust Structs | Pass Metadata/IDs, reconstruct in worker |
| Pydantic auto-coercion | Missing `to_dict` | Add `def to_dict(self): return self.model_dump()` |
| Direct Object Mutation | Intercepted by Proxy | Works seamlessly, but creates Shadow Copy behind scenes |

## 5. Standard Data Access Patterns

Unlike standard Python objects, Theus ContextGuard supports multiple access patterns via Duck Typing to bridge the Rust-Python gap.

### Reading Data

```python
# 1. Object Access (Recommended)
# Best for readability and IDE support (if typed)
val = ctx.domain.user.name

# 2. Dict Access (Supported via Proxy)
# Useful for dynamic keys
val = ctx.domain['user']['name']

# 3. Safe Access
# Best for optional fields
val = ctx.domain.get('missing_key', 'default')
```
*   *Note*: Accessing a nested object returns a `SupervisorProxy` wrapper, not a raw dict.

## 6. Mutation Patterns (Writing)

All writes are intercepted by the Transaction Manager.

### Field & Key Assignment

```python
# 1. Field Assignment
ctx.domain.status = "ACTIVE"

# 2. Key Assignment
ctx.domain['counter'] = 101

# 3. Bulk Update (If object has .update method)
# Works because Proxy delegates the method call to the Shadow Copy
ctx.domain.config.update({"timeout": 500, "retry": 3})
```

### Collection Mutation (Lists/Sets)
Methods that mutate in-place are fully supported and tracked by the Transaction engine.

```python
# List append
# WARNING: Ensure you are not violating "FrozenList" constraints (See Chapter 5)
# This works only if you have Write Permissions (outputs=...)
ctx.domain.items.append("new_item")

# List extend
ctx.domain.logs.extend(["log1", "log2"])

# Pop/Remove
item = ctx.domain.queue.pop(0)
```

## 7. Iteration & Type Checking Constraints

1.  **Iterating:** You can iterate directly: `for item in ctx.domain.items: ...`
2.  **Type Checking:** Do **NOT** use `isinstance(ctx.domain, dict)`. Use `hasattr` or `.to_dict()`.
