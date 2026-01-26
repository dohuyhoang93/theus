# Chapter 9: Audit Levels & Thresholds

## 1. Action Hierarchy Table
Level defines **WHAT ACTION** the Engine will take when a rule is violated.

| Level | Name | Exception | Engine Action | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| **S** | **Safety Interlock** | `AuditStopError` | **Emergency Stop** | Stops entire System/Workflow. No further execution allowed. Used for Safety risks. |
| **A** | **Abort** | `AuditAbortError` | **Hard Stop** | Code-wise same as S, but semantic is "Critical Logic Error". Stops Workflow. |
| **B** | **Block** | `AuditBlockError` | **Rollback** | Rejects this Process only. Transaction cancelled. Workflow **STAYS ALIVE** and can retry or branch. |
| **C** | **Campaign** | (None) | **Log Warning** | Only logs yellow warning. Process still Commits successfully. |

> **🧠 Philosophy Note:** "Transparency is the Ultimate Value." By configuring thresholds (S/A/B), we make the system's tolerance **explicit** and **visible** in config, rather than buried in `if/else` checks. See Principle 1.2 of the [POP Manifesto](../../POP_Manifesto.md).

## 2. Dual-Thresholds: Error Accumulation
Real systems have Noise. Theus v3.0 allows you to configure "Tolerance" via Thresholds (Rust Audit Tracker).

### How Threshold Works
Each Rule has its own Counter in `AuditTracker`.
- **min_threshold:** Count to start Warning (Yellow).
- **max_threshold:** Count to trigger Punishment (Red Action - S/A/B).

**Example:** `max_threshold: 3`.
- 1st Error: Allow (or Warn if >= min).
- 2nd Error: Allow.
- 3rd Error: **BOOM!** Trigger Level (e.g., Block).
- After "BOOM", counter resets to 0.

### Important: Flaky Detection & Reset Strategy
Theus allows you to choose how strictly to track errors over time using the `reset_on_success` parameter.

#### 1. Standard Mode (Default)
`reset_on_success: true`
- If a process succeeds, the error counter is wiped clean (Reset to 0).
- **Use case:** Transient network glitches that resolve themselves immediately. You only care if errors happen *consecutively* (e.g., 3 fails in a row).

#### 2. Strict Accumulation Mode (Flaky Detector)
`reset_on_success: false`
- The counter **NEVER resets** automatically (until max_threshold is hit).
- **Use case:** Detecting "Flaky" components that fail 10% of the time but pass on retry.
- **Example:** Fails on run 1, Passes run 2, Fails run 3.
    - Standard Mode: Sees "1 error", then "0 errors", then "1 error". System stays green forever.
    - Flaky Detector: Sees "1 error", then "1 error" (legacy), then "2 errors". Eventually hits limit and Blocks.

## 3. Catching Errors in Orchestrator

```python
from theus_core import AuditBlockError, AuditAbortError, AuditStopError

try:
    engine.execute(add_product, price=-5)
except AuditBlockError:
    print("Blocked softly, retrying later...")
except AuditAbortError:
    print("Workflow aborted! Check logs.")
except AuditStopError:
    print("EMERGENCY STOP! CALL FIRE DEPT!")
    sys.exit(1)
```

---
**Exercise:**
Configure `max_threshold: 3` for rule `price >= 0`. Call consecutively with negative price and observe the 3rd call failing.

---

## 4. Design Decision: "Trust on Read, Verify on Write"

You might ask: *"Why doesn't Theus check if `domain.items` is valid when I read it?"*

**The Answer:** Performance & Philosophy.

1.  **Trust on Read:** Theus assumes data in the State is **already clean**. Why? Because it had to pass the strict **Write Audit** to get there in the previous tick.
    *   *Analogy:* You scan your badge to verify identity when *entering* a secure building (Write). You don't scan it every time you walk into the cafeteria (Read).
    *   **Access Control:** We DO check permissions (Can you read this?).

2.  **Verify on Write:** The "Gatekeeper" stands at the exit. Before any change is committed to the database, it must pass the Schema Audit.

> **⚠️ Performance Warning:** If we audited every Read, a loop iterating 10,000 items would trigger 10,000 Audit Logs. This would destroy performance (100x slowdown).
> **Rule:** If you need to validate inputs (e.g., from an external API), do it explicitly in your Python code:
> ```python
> if input_val < 0: raise ValueError("Bad Input")
> ```
