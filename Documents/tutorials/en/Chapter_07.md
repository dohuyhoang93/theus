# Chapter 7: Data Access & Common Pitfalls

Working with Immutable Snapshots requires a shift in thinking. This chapter helps you avoid common mistakes.

## 1. FrozenList & FrozenDict
When you access `ctx.domain_ctx.items`, Theus returns a **FrozenList**.
This is a zero-copy view of the Rust memory.

**Rule:** `FrozenList` is Read-Only.
- `items[0]` ✅ OK
- `items.append(x)` ❌ Output: `AttributeError`

To modify, you must **Copy** -> **Modify** -> **Return**.

> **🧠 Manifesto Connection:**
> **Principle 2.1: "Zero Trust Memory".**
> By forcing you to copy data before modifying, Theus ensures the "Original" version remains pristine for other parallel processes. This eliminates **Share-by-Reference Race Conditions** entirely.

## 2. The "Stale Reference" hazard

```python
# CODE
snapshot_items = ctx.domain_ctx.items  # Reference to Version N
# ... Process runs for 5 seconds ...
# ... Meanwhile, another process might have updated the state to Version N+1 ...

# Later in logic:
decision = make_decision(snapshot_items) 
```

**Risk:** `snapshot_items` is accurate for Version N, but might be stale by the time you act.
**Mitigation:** Theus uses **Optimistic Concurrency (CAS)**. If the underlying data changed while you were processing, your internal logic is self-consistent (Snapshot Isolation), but the Engine might reject your commit if it detects a conflict (depending on policy).

For most logic, this is a **feature**, not a bug: You always see a consistent world view.

**Advice:** Always access directly `ctx.domain_ctx.items` when needed. Do not cache it in local variables for too long.

> **Why this is a Superpower:**
> In normal Python, if `snapshot_items` changed under your feet, your report would be half-correct (corrupted state).
> In Theus, you are guaranteed that `snapshot_items` is internally consistent (Snapshot Isolation). Your report might be "old", but it will never be "broken".



Variables with `heavy_` prefix bypass the transaction log entirely:

```python
@process(outputs=['domain_ctx.heavy_embeddings'])
def compute_embeddings(ctx):
    # Direct write, no rollback protection
    # Valid: Return Heavy Update
    return "Processed", huge_numpy_array
```

## 3. Allocating Shared Memory (`engine.heavy.alloc`)

To truly use Zero-Copy, allocation should happen once (usually at startup).

```python
# Main Thread
tensor = engine.heavy.alloc("my_tensor", shape=(1024, 1024), dtype="float32")

# Commit handle to State
engine.compare_and_swap(engine.state.version, heavy={"global_tensor": tensor})
```

## 4. Using `StateUpdate` (Recommended)

For complex updates involving Heavy data, use `StateUpdate`.

```python
from theus.structures import StateUpdate

@process(outputs=['heavy.processed_image'])
def filter_image(ctx):
    # ... modification in place ...
    return StateUpdate(heavy={'processed_image': ctx.heavy.raw_image})
```

**Trade-off:** If process fails after this write, heavy data is NOT rolled back (dirty write). Use only for large data where speed > atomicity.

---
**Exercise:**
Try creating a global variable `G_CACHE = []` in python file.
In process 1: `G_CACHE = ctx.domain_ctx.items`.
After process 1 finishes, try accessing `G_CACHE` externally. Observe if data inside is still consistent with current `sys_ctx.domain_ctx.items`?
