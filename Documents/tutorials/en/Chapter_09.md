# Chapter 9: Severity Levels - The Hierarchy of Punishment

In Theus v2, Level is not just a log label. It defines exactly **WHAT ACTION** the Engine will take.

## 1. Action Hierarchy Table

| Level | Name | Exception | Engine Action | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| **S** | **Safety Interlock** | `AuditInterlockError` | **Emergency Stop** | Stops entire System/Workflow. No further execution allowed. Used for Safety risks. |
| **A** | **Abort** | `AuditInterlockError` | **Hard Stop** | Code-wise same as S, but semantic is "Critical Logic Error". Stops Workflow. |
| **B** | **Block** | `AuditBlockError` | **Rollback** | Rejects this Process only. Transaction cancelled. Workflow **STAYS ALIVE** and can retry or branch. |
| **C** | **Campaign** | (None) | **Log Warning** | Only logs yellow warning. Process still Commits successfully. |
| **I** | **Ignore** | (None) | **Silent** | Do nothing. |

## 2. When to use what?
- Use **S** for Physical Limits (Temp, Pressure, Max Memory).
- Use **A** for Unrecoverable Data Errors (Lost DB connection, Corrupt data).
- Use **B** for Business Rules (Invalid format, Insufficient funds, Duplicate name).
- Use **C** for KPIs (Execution slightly slow, Value slightly high but acceptable).

## 3. Catching Errors
In Control Logic (Orchestrator):
```python
try:
    engine.run_process("add_product", ...)
except AuditBlockError:
    print("Blocked softly, retrying later...")
except AuditInterlockError:
    print("EMERGENCY STOP! CALL FIRE DEPT!")
    sys.exit(1)
```

---
**Exercise:**
Try configuring Audit Level `S`. Violate it and observe `AuditInterlockError`. Try configuring `B` and observe `AuditBlockError`. Write `try/except` code to handle these 2 cases differently.
