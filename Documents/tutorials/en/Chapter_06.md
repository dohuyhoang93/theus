# Chapter 6: Transaction & Delta - The Time Machine v2

In Theus v2, the Transaction concept is handled by the **Rust Core**, ensuring absolute data integrity (ACID-like) with optimized performance.

## 1. Core Philosophy: Why we "Hold" the Context?
You might wonder: *"Why does Theus keep a reference to the entire context instead of just copying what I asked for?"*

The answer lies in **Safety** and **Atomicity**.
*   **Preventing Contract Cheating:** If we only copied the declared `outputs`, a malicious or buggy process could secretly modify a variable it *didn't* declare (Side Effect). By wrapping the entire context in a Transaction, Theus ensures that *all* writes go to a temporary "Shadow State". Only declared outputs are committed back; undeclared changes are discarded.
*   **Atomic Rollback:** To guarantee that a system state is either "All New" or "All Old", Theus creates a sandbox. If a process crashes halfway, the Sandbox is destroyed, and the original system remains untouched.

## 2. Two Transaction Strategies (Hybrid Engine)
Theus uses a Hybrid Approach to optimize performance automatically:

### 2.1. Optimistic Concurrency (Scalar: int, str, bool)
When you assign `ctx.counter = 10`:
- **Action:** In-place update (Fast).
- **Insurance:** Theus logs the *Inverse Operation* to `DeltaLog` ("Old value was 5").
- **Rollback:** Reads log backwards to restore state.

### 2.2. Shadow Copy (Collection: list, dict)
When you modify `ctx.items`:
- **Action:** Theus creates a replica (Shadow).
- **Operation:** You work on the Shadow.
- **Commit:** Content is swapped back to original if success.
- **Rollback:** Shadow is dropped. Original is safe.

## 3. The Audit Log: Transient & Ephemeral
A critical design choice in Theus is that **Transaction Logs are Ephemeral**.
*   **While Running:** The log exists to track every change.
*   **After Success:** The log is **discarded** (Dropped).
*   **Why?** Storing full data history (especially for AI Tensors) would explode memory instanty. Theus is designed to be "Audit-Aware" (counting violations) rather than a full "Time-Travel Database" for storage.

---
**Advanced Sabotage Exercise:**
In `add_product` process:
1. Set `sig_restock_needed = True`.
2. Append an item to the list.
3. Raise Exception at end of function.
4. Check if `sig_restock_needed` reverts to `False` and item disappears from list after crash.
