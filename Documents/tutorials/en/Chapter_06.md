# Chapter 6: Transaction & Delta - The Time Machine v3

In Theus v3.0, the Transaction concept is handled by the **Rust Core**, ensuring absolute data integrity (ACID-like) with optimized performance.

## 1. Core Philosophy: Why we "Hold" the Context?
You might wonder: *"Why does Theus keep a reference to the entire context instead of just copying what I asked for?"*

The answer lies in **Safety** and **Atomicity**.
*   **Preventing Contract Cheating:** If we only copied the declared `outputs`, a malicious or buggy process could secretly modify a variable it *didn't* declare (Side Effect). By wrapping the entire context in a Transaction, Theus ensures that *all* writes go to a temporary "Shadow State". Only declared outputs are committed back; undeclared changes are discarded.
*   **Atomic Rollback:** To guarantee that a system state is either "All New" or "All Old", Theus creates a sandbox. If a process crashes halfway, the Sandbox is destroyed, and the original system remains untouched.

## 2. Snapshot Isolation Strategy (v3.0)
Theus v3.0 moves away from "In-Place Mutation" to a **Snapshot Isolation** model:

### 2.1. The Immutable Snapshot
When a Process starts, it receives a **Restricted View** (Snapshot) of the Context.
- **READ:** Fast, Lock-free access to data at `version=N`.
- **WRITE:** Strictly prohibited on the Snapshot object.

### 2.2. Copy-on-Write (CoW)
To modify data, you must:
1. **Copy:** Create a new instance (e.g., `new_list = list(old_list)`).
2. **Compute:** Modify the new instance.
3. **Return:** Send the new instance back to the Engine.

### 2.3. Atomic Commit
The Engine receives your Return Value and performs:
- **Validation:** Checks if `version` is still `N` (Optimistic Lock).
- **Swap:** Replaces the pointer `Arc<State>` with the new state.
- **Rollback:** If Exception occurs before Return, the new data is simply discarded. The original State was never touched.

> [!CAUTION]
> **Safety Violation:** If you perform In-Place Mutation (e.g., `ctx.domain.list.append()`) instead of Copy-on-Write, you are modifying the "Original State" directly.
> In this case, **Rollback CANNOT save you**. The corrupt data is already in memory.


## 3. Transaction Context Manager (v3.0)

```python
with engine.transaction() as tx:
    # Operations here are transactional
    tx.update(data={'counter': 10})
    
# Auto-commit on success, auto-rollback on exception
```

## 4. Compare-and-Swap Pattern (v3.0)

For optimistic concurrency control:

```python
# Get current version
current_version = engine.state.version

# Perform optimistic update
try:
    engine.compare_and_swap(
        expected_version=current_version,
        data={'counter': new_value}
    )
except VersionMismatchError:
    # Someone else modified state, retry
    pass
```

## 5. The Audit Log: Transient & Ephemeral
A critical design choice in Theus is that **Transaction Logs are Ephemeral**.
*   **While Running:** The log exists to track every change.
*   **After Success:** The log is **discarded** (Dropped).
*   **Why?** Storing full data history (especially for AI Tensors) would explode memory instantly. Theus is designed to be "Audit-Aware" (counting violations) rather than a full "Time-Travel Database" for storage.

---
**Advanced Sabotage Exercise:**
In `add_product` process:
1. Set `sig_restock_needed = True`.
2. Append an item to the list.
3. Raise Exception at end of function.
4. Check if `sig_restock_needed` reverts to `False` and item disappears from list after crash.
