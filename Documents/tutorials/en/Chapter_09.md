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

### YAML Configuration Example
```yaml
# audit_recipe.yaml
audit:
  level: "Block"           # or "Stop", "Abort", "Count" (S/A/B/C also accepted)
  threshold_min: 2         # Warning threshold
  threshold_max: 5         # Block threshold
  reset_on_success: true   # Standard mode (false = Flaky Detector)
```

Then load it:
```python
from theus.config import ConfigFactory
from theus import TheusEngine

recipe = ConfigFactory.load_recipe("audit_recipe.yaml")
engine = TheusEngine(context={...}, audit_recipe=recipe)
```

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
from theus.audit import AuditBlockError, AuditAbortError, AuditStopError

try:
    await engine.execute(add_product, price=-5)
except AuditBlockError:
    print("Blocked softly, retrying later...")
except AuditAbortError:
    print("Workflow aborted! Check logs.")
except AuditStopError:
    print("EMERGENCY STOP! CALL FIRE DEPT!")
    sys.exit(1)
```

**Note:** These exceptions are re-exported from `theus.audit` for convenience. You can also import directly from `theus_core` if needed.

---
**Exercise:**
Configure `max_threshold: 3` for rule `price >= 0`. Call consecutively with negative price and observe the 3rd call failing.

---

## 4. Design Decision: "Dual Gate Validation"

Theus validates data at **two checkpoints** to ensure system integrity:

### 4.1 Input Gate (Before Execution)
When you call a process with arguments, Theus validates them **before** execution begins.

```python
# audit_recipe.yaml
process_recipes:
  p_signup:
    inputs:
      - field: "age"
        min: 18
        message: "User must be 18+"
```

```python
# This fails at Input Gate (before signup logic runs)
await engine.execute(p_signup, age=15)  # AuditBlockError
```

**What happens:**
1. `validate_inputs()` checks `age >= 18`
2. Violation detected → `audit_system.log_fail("p_signup:input:age")`
3. Counter increments; if threshold exceeded → Process **blocked**
4. Signup logic **never executes** (failed at gate)

### 4.2 Output Gate (Before Commit)
After a process returns data, Theus validates the **pending mutations** before committing to state.

```python
# audit_recipe.yaml
process_recipes:
  p_update_score:
    outputs:
      - field: "domain.score"
        max: 200
        message: "Score overflow"
```

```python
@process(outputs=["domain.score"])
async def p_update_score(ctx):
    return 250  # Invalid!

# This fails at Output Gate (before CAS commit)
await engine.execute(p_update_score)  # AuditBlockError
```

**What happens:**
1. Process executes, returns `250`
2. `validate_outputs()` checks `score <= 200`
3. Violation detected → Audit logs, counter increments
4. CAS **never commits** (state unchanged)

### 4.3 Performance Considerations

**Q:** *"Won't validating inputs slow down my loops?"*

**A:** No. Validation runs **once per process call**, not per-read inside loops.

```python
@process(inputs=["domain.items"])
async def analyze_items(ctx):
    # Input Gate validates 'items' ONCE here
    
    total = 0
    for i in range(10000):
        # NO validation here (just normal dict access)
        total += ctx.domain.items[i]
    
    return total
```

**Performance:** Validation overhead is O(1) per `execute()`, regardless of loop iterations inside the process.

**External API Inputs:** Always validate untrusted data explicitly:
```python
if external_age < 0:
    raise ValueError("Invalid age from API")
```
