# Module 05: Audit System

> **For AI Assistants:** The Audit System enforces business rules at runtime. It acts as a traffic police for data operations.

---

## 1. Audit System Overview

The Audit System provides:
- **Rule-based Validation:** Check inputs/outputs against defined rules
- **Severity Levels:** Different actions based on violation severity
- **Threshold Tracking:** Accumulate errors before triggering action
- **Ring Buffer Logging:** Efficient, bounded audit trail

---

## 2. Audit Levels

| Level | Name | Exception | Action | Use Case |
|:------|:-----|:----------|:-------|:---------|
| **S** | Safety | `AuditStopError` | Emergency STOP | Critical safety violations |
| **A** | Abort | `AuditAbortError` | Hard STOP workflow | Critical logic errors |
| **B** | Block | `AuditBlockError` | Rollback transaction | Recoverable errors |
| **C** | Count | None | Log warning only | Monitoring, metrics |

### Level Behavior

```
Level S/A → System/Workflow STOPS completely
Level B   → Transaction rolls back, workflow continues
Level C   → Nothing happens, just logged
```

---

## 3. Audit Recipe YAML

```yaml
# specs/audit_recipe.yaml

# Global default settings
default_level: "B"
default_threshold_max: 3
default_threshold_min: 1

# Per-process rules
process_recipes:
  transfer_funds:
    inputs:
      - field: "amount"
        min: 0
        max: 10000
        level: "B"
        
    outputs:
      - field: "domain_ctx.balance"
        min: 0
        level: "S"  # Safety: balance can never be negative
        
  login_attempt:
    inputs:
      - field: "password"
        regex: "^.{8,}$"  # Min 8 chars
        level: "B"
        
    # Threshold for brute force protection
    threshold_max: 5
    threshold_min: 3
    reset_on_success: false
```

### Rule Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `field` | string | Path to field being validated |
| `min` | number | Minimum allowed value |
| `max` | number | Maximum allowed value |
| `regex` | string | Regex pattern for strings |
| `level` | string | S/A/B/C severity |

---

## 4. Threshold System

### Dual Thresholds

```yaml
threshold_min: 2    # Start warning at 2 errors
threshold_max: 5    # Block at 5 errors
reset_on_success: true
```

**Behavior:**
```
Error 1: OK (count = 1)
Error 2: WARNING (count >= min)
Error 3: WARNING
Error 4: WARNING
Error 5: BLOCK! (count >= max, triggers level action)
         Counter resets to 0
```

### Reset Modes

| Mode | Config | Behavior |
|:-----|:-------|:---------|
| **Standard** | `reset_on_success: true` | Counter resets on successful process |
| **Flaky Detector** | `reset_on_success: false` | Counter never resets until max hit |

**Use Flaky Detector for:**
- Components that fail intermittently
- Detecting unreliable external services
- Long-term error accumulation

---

## 5. Loading Audit Recipe

```python
from theus import TheusEngine

# From file
engine = TheusEngine(
    sys_ctx,
    strict_mode=True,
    audit_recipe="specs/audit_recipe.yaml"
)

# From dict
audit_config = {
    "process_recipes": {
        "my_process": {
            "inputs": [
                {"field": "value", "min": 0, "max": 100, "level": "B"}
            ]
        }
    }
}
engine = TheusEngine(sys_ctx, audit_recipe=audit_config)
```

---

## 6. Rust Audit Classes

```python
from theus_core import (
    AuditSystem,
    AuditRecipe,
    AuditLevel,
    AuditLogEntry,
    AuditBlockError,
    AuditAbortError,
    AuditStopError,
    AuditWarning
)
```

### AuditLevel Enum

```python
class AuditLevel:
    Stop = 0   # Level S
    Abort = 1  # Level A
    Block = 2  # Level B
    Count = 3  # Level C
```

### AuditRecipe

```python
recipe = AuditRecipe(
    level=AuditLevel.Block,
    threshold_max=5,
    threshold_min=2,
    reset_on_success=True
)
```

### AuditSystem

```python
# Create audit system
audit = AuditSystem(recipe=recipe, capacity=1000)

# Log failure
try:
    audit.log_fail("login_attempt")  # Increments counter
except AuditBlockError:
    print("Blocked after too many failures")

# Log success
audit.log_success("login_attempt")  # Resets counter if configured

# Query
count = audit.get_count("login_attempt")
total = audit.get_count_all()
logs = audit.get_logs()  # List[AuditLogEntry]
```

---

## 7. Exception Handling Pattern

```python
from theus_core import (
    AuditBlockError,
    AuditAbortError, 
    AuditStopError
)

try:
    engine.execute(risky_process, amount=50000)
    
except AuditBlockError as e:
    # Level B: Transaction rolled back, can retry
    print(f"Blocked: {e}")
    # Retry with different parameters
    
except AuditAbortError as e:
    # Level A: Workflow must stop
    print(f"Aborted: {e}")
    # Graceful shutdown
    
except AuditStopError as e:
    # Level S: Emergency stop
    print(f"EMERGENCY: {e}")
    sys.exit(1)
```

---

## 8. Ring Buffer (Audit Log)

Audit logs are stored in a fixed-size ring buffer to prevent memory explosion.

```python
# Capacity set at initialization
audit = AuditSystem(capacity=1000)

# Logs
audit.log("transfer", "Transferred $500 to Bob")

# Retrieve (returns List[AuditLogEntry])
logs = audit.get_logs()

for entry in logs:
    print(entry)  # Formatted log string
    
# Buffer size
size = audit.ring_buffer_len()
```

**Behavior:**
- When buffer is full, oldest entries are overwritten
- O(1) insert, O(n) retrieval
- Thread-safe (Mutex protected)


---

## 9. Monitoring & Inspection

Since the Audit System is "Silent by Default", use the following API to inspect results at runtime:

```python
if engine._audit:
    # 1. Get full log history (List[AuditLogEntry])
    logs = engine._audit.get_logs()
    
    print(f"--- Audit History ({len(logs)} entries) ---")
    for entry in logs:
        # entry.timestamp (float), entry.key (str), entry.message (str)
        print(f"[{entry.timestamp:.2f}] {entry.key}: {entry.message}")

    # 2. Get specific failure count
    fail_count = engine._audit.get_count("process_name")
    
    # 3. Get total activity count
    total_ops = engine._audit.get_count_all()
```

**Note:** `engine._audit` is `None` if no `audit_recipe` was provided/loaded.

---

## 10. Complete Audit Recipe Example

```yaml
# specs/banking_audit.yaml

default_level: "B"
default_threshold_max: 3

process_recipes:
  # Wire transfer with strict limits
  wire_transfer:
    inputs:
      - field: "amount"
        min: 1
        max: 100000
        level: "B"
      - field: "recipient_account"
        regex: "^[A-Z]{2}[0-9]{20}$"  # IBAN format
        level: "B"
    outputs:
      - field: "domain.sender_balance"
        min: 0
        level: "S"  # Safety: prevent negative balance
    threshold_max: 1  # No retries for wire transfers
    
  # Login with brute force protection
  user_login:
    inputs:
      - field: "password"
        regex: "^.{8,64}$"
        level: "B"
    threshold_min: 3
    threshold_max: 5
    reset_on_success: false  # Accumulate over time
    
  # Daily report (relaxed)
  generate_report:
    outputs:
      - field: "domain_ctx.report_size"
        max: 10000000  # 10MB limit
        level: "C"  # Just warn, don't block
```

---

## 10. AI Implementation Checklist

When generating Audit configuration:

- [ ] Define `default_level` (usually "B")
- [ ] Set appropriate `threshold_max` per process
- [ ] Use Level S only for safety-critical violations
- [ ] Use Level B for recoverable errors
- [ ] Use Level C for monitoring/metrics
- [ ] Set `reset_on_success: false` for flaky detection
- [ ] Keep regex patterns simple and tested
- [ ] Set reasonable `capacity` for ring buffer

---

*Next: [06_ADVANCED_PATTERNS.md](./06_ADVANCED_PATTERNS.md)*
