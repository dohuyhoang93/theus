# Chapter 5: ContextGuard & Zone Enforcement - Iron Discipline

In this chapter, we dive deep into Theus v3.0's protection mechanisms: **SupervisorProxy** and **Zone Enforcement**.

## 1. The Proxy Architecture
This is the core principle: **"Transparent Isolation."**

### Inputs (Protected)
When you read data from Context with only read permission (`inputs`):
- The Engine returns **Native Rust Views** (e.g., `FrozenList`, `FrozenDict`).
- Modification methods (`append`, `pop`, `update`, `__setitem__`) are disabled in the Rust layer.
- *Performance:* Zero-copy read directly from the state snapshot.

### Outputs (Unlocked & Proxyed)
When you have write permission (`outputs`), Theus wraps the object in a `SupervisorProxy`:
1.  **Transparent Access**: It behaves like a normal Python object/dict.
2.  **Lazy Shadowing**: The moment you attempt a write (or mutable access), it creates a **Shadow Copy** in the Python Heap.
3.  **Automatic Merging**: When the process finishes, Theus diffs the Shadow Copy against the original and commits the changes.

```python
# ✅ MODERN V3.0 PATTERN (Transparent Mutation)
@process(outputs=['domain.items'])
async def add_item(ctx):
    # ctx.domain.items is unlocked via Proxy
    ctx.domain.items.append("New Thing")
    # No return needed! The proxy tracks the modification.
```

## 2. Zone Enforcement (The Zone Police)
The Guard checks not just permissions, but **Architecture**.

### Input Guard
In `ContextGuard` initialization, Theus v3.0 checks all `inputs`:
- **Rules**: You cannot use `SIGNAL` or `META` as logical inputs for Business Data.
- This prevents Process logic from depending on non-persistent or diagnostic values.

### Output Guard
Conversely, you are allowed to write to any Zone (Data, Signal, Meta) as long as you declare it in `outputs`.

## 3. Zone Prefix Reference

| Zone | Prefix | Behavior |
|:-----|:-------|:---------|
| DATA | (none) | Transactional, Rollback on error |
| SIGNAL | `sig_`, `cmd_` | Transient, Ephemeral |
| META | `meta_` | Observability only |
| HEAVY | `heavy_` | Large data, Zero-copy, NO rollback |

## 4. The "Stale Reference" Trap
Even with Proxies, there is one rule you MUST follow: **"Do not cache state pointers."**

```python
# ❌ DANGEROUS CODE
@process(outputs=['domain.items'])
async def bad_proc(ctx):
    items = ctx.domain.items # Snapshot A
    await call_other_process() # Moves state to Snapshot B
    items.append(1) # WRITES TO DEAD SNAPSHOT A! Changes lost.
```

> [!TIP]
> **Trust the Proxy**
> Always access data directly via `ctx.domain...` at the moment of use. The `SupervisorProxy` ensures you always see the latest transactional view.

---
**Exercise:**
Try to "hack" the Guard.
1. Declare `inputs=['domain.items']` (but NO outputs).
2. Inside the function, try calling `ctx.domain.items.append(1)`.
3. Observe the `TypeError` or `ContextError` to witness Theus's protection.
