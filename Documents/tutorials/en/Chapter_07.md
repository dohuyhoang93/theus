# Chapter 7: Data Access & Common Pitfalls

Working with Immutable Snapshots requires a shift in thinking. This chapter helps you avoid common mistakes.

## 1. Protected Views vs. Proxies
In Theus v3.0, the framework automatically chooses the safest way to expose data.

### Read-Only (`inputs` only)
When you access `ctx.domain.items` (a list) without write permission:
- Theus returns a **Detached Copy** (Raw List) from the Rust memory.
- **Behavior:** `items.append(x)` **SUCCEEDS locally** (in memory).
- **Safety:** The Engine **REJECTS** this change during the Commit phase (Contract Violation) or simply discards it.
- **Warning:** Do not rely on "Immutable Errors" to catch logic bugs inside the function. The failure happens at the end.

### Writable (`outputs` declared)
When you have permission:
- Theus returns a **SupervisorProxy**.
- **Rule:** You can mutate in-place. `ctx.domain.items.append(x)` works natively.
- The Engine handles the deep copy and transactional merge for you.

> **🧠 Manifesto Connection:**
> **Principle 2.1: "Zero Trust Memory".**
> By intercepting access via Proxies, Theus ensures the "Original" state remains pristine for other parallel processes. You are always modifying a private shadow until you commit.

## 2. The "Stale Reference" Hazard

```python
# ❌ STALE PATTERN
async def my_proc(ctx):
    items = ctx.domain.items  # Snapshot A
    await call_other_process() # Moves system to Snapshot B
    items.append(1) # WRITES TO DEAD SNAPSHOT A!
```

**Advice:** Always access directly `ctx.domain.items` at the moment of modification. Do not cache the proxy object across `await` boundaries if other processes might update the state.

## 3. Allocating Shared Memory (`engine.heavy.alloc`)

Heavy variables (`heavy_` prefix) bypass the transaction log for speed.

```python
# 1. Main Thread: Allocate Managed Memory
# No manual unlink/cleanup needed.
tensor = engine.heavy.alloc("my_tensor", shape=(1024, 1024), dtype="float32")

# 2. Inject into State
await engine.compare_and_swap(engine.state.version, heavy={"global_tensor": tensor})
```

## 4. Why use `StateUpdate`?

While Proxies handle lists/dicts, `StateUpdate` is recommended for complex bulk updates or switching between different large memory segments.

```python
from theus.structures import StateUpdate

@process(outputs=['heavy.processed_image'])
async def filter_image(ctx):
    # Perform compute...
    # Return explicit update for the heavy zone
    return StateUpdate(heavy={'processed_image': ctx.heavy.raw_image})
```

---
**Exercise:**
Try creating a global variable `G_CACHE = []` in your script.
In a Process: `G_CACHE = ctx.domain.items`.
After the process finishes, check if `G_CACHE` still works. Observe how `SupervisorProxy` prevents "accidental persistence" outside transactions.
