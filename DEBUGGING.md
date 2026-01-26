# Debugging & Troubleshooting Theus v3

Theus v3 employs a strict **Process-Oriented Programming (POP)** architecture with **Rust Core** enforcement. This means it behaves differently than standard Python frameworks. This guide explains the common "gotchas" and how to solve them.

---

## 1. SupervisorProxy & Type Checking

### The Core Concept
When you access `ctx.domain`, you get a `SupervisorProxy`, NOT a direct reference to your object.
*   **Why?** To track mutations (for Audit/Rollback) and strictly enforce read-only/write access.
*   **The Trap:** `isinstance(ctx.domain, dict)` returns `False`.

### Common Error
```python
req = ctx.domain['request']
if isinstance(req, dict): # FAILS
    ...
```

### The Fix
Use **Duck Typing** or convert explicitly if needed.

**Option A: Trust the Proxy (Recommended)**
The Proxy mimics the wrapped object. Just use `.get()`, `[]`, or iteration as if it were the real thing.
```python
# Instead of type checking:
req = ctx.domain['request']
val = req.get('key') # Works!
```

**Option B: Unwrap (If strict lib requires it)**
If you pass data to a library (e.g., Pydantic, JSON serializer) that strictly checks types:
```python
req = ctx.domain['request']
if hasattr(req, 'to_dict'):
    req = req.to_dict() # Returns a CLEAN Python dict copy
```

---

## 2. Serialization & Pickling (The "State is Data" Rule)

### The Core Concept
Theus stores the Global State in Rust (`Arc<PyObject>`). To support functionalities like **Snapshots**, **Cluster Sync**, or **Deep Copies** (for audit), the state MUST be picklable/serializable.

### Common Error
`TypeError: cannot pickle '_asyncio.Task' object` (or similar for file handles, sockets, threads).

### The Fix
**NEVER store runtime objects in Domain State.**
*   ❌ Don't store: `asyncio.Task`, `threading.Thread`, Open Files, Database Connections.
*   ✅ Do store: IDs, Status Strings, File Paths, Configuration Dicts.

**Pattern: Ephemeral Registry**
If you need to track running tasks, use a module-level variable (Ephemeral State) and map it to IDs in the Persistent State.
```python
# Global Registry
_ACTIVE_TASKS = {} 

@process(...)
def spawn_job(ctx):
    task = asyncio.create_task(...)
    job_id = "job_123"
    _ACTIVE_TASKS[job_id] = task  # Store runtime obj here
    return {"job_id": job_id, "status": "RUNNING"} # Store DATA in State
```

---

## 3. Transactions & "Shadowing"

### The Core Concept
When a process runs, it sees a **Snapshot** of the world. Writes are buffered in a **Shadow Copy**.
*   **Read:** You see the version of data from when the transaction started.
*   **Write:** You write to a pending buffer.
*   **Read-Your-Writes:** You will SEE your own writes within the same transaction context.

### Common Confusion
"I wrote to `ctx.domain` but `ctx.domain` didn't change!"
*   **Isolation:** The global state ONLY updates when the process returns successfully (Commit).
*   **Conflict:** If another process updated the same key in parallel, your commit might trigger a CAS Retry loop.

---

## 4. Helpful Debugging Tools

### Check your type
```python
print(type(ctx.domain)) 
# <class 'theus_core.SupervisorProxy'>
```

### Inspect Rust Wrapper
```python
print(repr(ctx.domain))
# <SupervisorProxy[dict] at path='domain'>
```

### Export State for Inspection
```python
from theus.utils import dump_state
dump_state(engine.state) # Pretty print JSON
```
