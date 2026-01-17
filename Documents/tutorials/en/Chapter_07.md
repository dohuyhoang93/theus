# Chapter 7: Data Access & Common Pitfalls

Working with Immutable Snapshots requires a shift in thinking. This chapter helps you avoid common mistakes.

## 1. FrozenList & FrozenDict
When you access `ctx.domain_ctx.items`, Theus returns a **FrozenList**.
This is a zero-copy view of the Rust memory.

**Rule:** `FrozenList` is Read-Only.
- `items[0]` ✅ OK
- `items.append(x)` ❌ Output: `AttributeError`

To modify, you must **Copy** -> **Modify** -> **Return**.

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



Variables with `heavy_` prefix bypass the transaction log entirely:

```python
@process(outputs=['domain_ctx.heavy_embeddings'])
def compute_embeddings(ctx):
    # Direct write, no rollback protection
    # Valid: Return Heavy Update
    return "Processed", huge_numpy_array
```

**Trade-off:** If process fails after this write, heavy data is NOT rolled back (dirty write). Use only for large data where speed > atomicity.

---
**Exercise:**
Try creating a global variable `G_CACHE = []` in python file.
In process 1: `G_CACHE = ctx.domain_ctx.items`.
After process 1 finishes, try accessing `G_CACHE` externally. Observe if data inside is still consistent with current `sys_ctx.domain_ctx.items`?
