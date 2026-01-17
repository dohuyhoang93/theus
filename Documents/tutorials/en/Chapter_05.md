# Chapter 5: ContextGuard & Zone Enforcement - Iron Discipline

In this chapter, we dive deep into Theus v3.0's protection mechanisms: **Guard** and **Zone** (powered by Rust).

## 1. Immutability & Unlocking
This is the core principle: **"Everything is Immutable until Unlocked."**

### Frozen Structures (Rust)
When you read a List/Dict from Context with only read permission (`inputs`):
- Engine returns `FrozenList` or `FrozenDict` (Native Rust Types).
- Modification methods (`append`, `pop`, `update`, `__setitem__`) are disabled.
- You can only read (`get`, `len`, `iter`).
- *Performance:* Zero-copy view of the data.

### Copy-on-Write (Safe Mutation)
When you have write permission (`outputs`), you do **NOT** modify the Context directly.
Instead, you follow the **Copy-on-Write** pattern:
1.  Read the `FrozenList` from Context.
2.  Create a mutable local copy (Python `list()`).
3.  Modify the local copy.
4.  **Return** the new list (or let Theus map it to outputs).

```python
# ✅ CORRECT PATTERN
def add_item(ctx):
    current_items = ctx.domain.items  # Read FrozenList
    new_items = list(current_items)   # Copy to Mutable
    new_items.append("New Thing")     # Modify
    return new_items                  # Return for Commit
```

## 2. Zone Enforcement (The Zone Police)
The Guard checks not just permissions, but **Architecture**.

### Input Guard
In `ContextGuard` initialization, Theus v3.0 checks all `inputs`:
```rust
// Rust Core Logic
for inp in inputs {
    if is_signal_zone(inp) {
        return Err("Cannot use Signal as Input!");
    }
}
```
This prevents Process logic from depending on non-persistent values.

### Output Guard
Conversely, you are allowed to write to any Zone (Data, Signal, Meta) as long as you declare it in `outputs`.

## 3. Zone Prefix Reference

| Zone | Prefix | Behavior |
|:-----|:-------|:---------|
| DATA | (none) | Transactional, Rollback on error |
| SIGNAL | `sig_`, `cmd_` | Transient, Reset on read |
| META | `meta_` | Observability only |
| HEAVY | `heavy_` | Zero-copy, NO rollback |

## 4. Zero Trust Memory
Theus does not believe in "temporary variables".
```python
# Bad Code (Fails in v3.0)
my_list = ctx.domain_ctx.items
# ... do something long ...
my_list.append(x) # Error! 'FrozenList' object has no attribute 'append'
```
Theus blocks in-place mutation to force you to use the **Return Pattern**. This ensures all changes are explicit and auditable at the function boundary.
    
> [!WARNING]
> **The Zero-Copy Caveat (Crucial for V3)**
> To achieve Rust-like performance, Theus V3 uses **Zero-Copy Reads**.
> *   When you access `ctx.domain.items`, you get a direct view of the underlying memory.
> *   **Do NOT** attempt to mutate this object in-place (e.g., `items.append()`), even if Python allows it.
> *   If you do, you bypass the Transaction Rollback mechanism. If your process crashes later, the change **WILL PERSIST** (Data Corruption).
> *   **ALWAYS** use Copy-on-Write: `new_list = list(ctx.domain.items)`.


---
**Exercise:**
Try to "hack" the Guard.
1. Declare `inputs=['domain_ctx.items']` (but NO outputs).
2. Inside the function, try calling `ctx.domain_ctx.items.append(1)`.
3. Observe the `TypeError: 'FrozenList' object is immutable` to witness Theus's protection.
