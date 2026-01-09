# Chapter 5: ContextGuard & Zone Enforcement - Iron Discipline

In this chapter, we dive deep into Theus v2's protection mechanisms: **Guard** and **Zone** (powered by Rust).

## 1. Immutability & Unlocking
This is the core principle: **"Everything is Immutable until Unlocked."**

### Frozen Structures (Rust)
When you read a List/Dict from Context with only read permission (`inputs`):
- Engine returns `FrozenList` or `FrozenDict` (Native Rust Types).
- Modification methods (`append`, `pop`, `update`, `__setitem__`) are disabled.
- You can only read (`get`, `len`, `iter`).
- *Performance:* Zero-copy view of the data.

### Tracked Structures (Rust)
When you have write permission (`outputs`):
- Engine returns `TrackedList` or `TrackedDict`.
- Modification is allowed, but it logs to `Transaction Delta` instead of modifying the original data immediately (Shadow Mechanism).

## 2. Zone Enforcement (The Zone Police)
The Guard checks not just permissions, but **Architecture**.

### Input Guard
In `ContextGuard` initialization, Theus v2 checks all `inputs`:
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

## 3. Zero Trust Memory
Theus does not believe in "temporary variables".
```python
# Bad Code (Theus warns or blocks)
my_list = ctx.domain_ctx.items
# ... do something long ...
my_list.append(x) # Dangerous! my_list might be detached from Transaction
```
Theus encourages you to always access via `ctx.` to ensure you are interacting with the **latest Guard Proxy**.

---
**Exercise:**
Try to "hack" the Guard.
1. Declare `inputs=['domain_ctx.items']` (but NO outputs).
2. Inside the function, try calling `ctx.domain_ctx.items.append(1)`.
3. Observe the `TypeError: 'FrozenList' object is immutable` to witness Theus's protection.
