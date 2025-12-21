# Chapter 6: Transaction & Delta - The Time Machine v2

In Theus v2, the Transaction concept is upgraded to ensure absolute data integrity (ACID-like) right in Python memory.

## 1. Two Transaction Strategies
Theus uses a Hybrid Approach to optimize performance:

### 1.1. Optimistic Concurrency (For Scalar: int, str, bool)
When you assign `ctx.domain.counter = 10`:
- **Action:** Theus overwrites 10 to the Real Context **immediately** (In-place update).
- **Insurance:** Simultaneously, Theus logs to `DeltaLog`: *"Old value of counter was 5"*.
- **Rollback:** If error, Theus reads Log backwards and restores old values.
- **Benefit:** Extremely fast for simple variables.

### 1.2. Shadow Copy (For Collection: list, dict)
When you modify `ctx.domain.items`:
- **Action:** Theus creates a replica (Shadow) of that list.
- **Operation:** All your `append`, `pop` commands happen on this Shadow. The original List knows nothing.
- **Commit:** If success, Theus swaps the Shadow content into the Original List.
- **Rollback:** If error, Shadow is discarded. Original List remains pristine.
- **Benefit:** Safe for complex data structures, prevents "half-modified" lists.

## 2. Automatic Commit & Rollback
You never have to call `commit()` or `rollback()` manually. The Engine handles it.

```python
try:
    # 1. Start Tx
    # 2. Run Process
    # 3. Audit Output -> If OK -> Commit
except Exception:
    # 4. Rollback
```

## 3. Signal Zone in Transaction
An interesting point of Theus v2: **Signals are also affected by Transaction**.
- If you set flag `sig_alarm = True`.
- Then Process crashes -> Rollback.
- `sig_alarm` will automatically revert to `False` (or old value).
This ensures no "False Alarms" from a failed process.

---
**Advanced Sabotage Exercise:**
In `add_product` process:
1. Set `sig_restock_needed = True`.
2. Append an item to the list.
3. Raise Exception at end of function.
4. Check if `sig_restock_needed` reverts to `False` and item disappears from list after crash.
