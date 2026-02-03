# Chapter 8: Audit System V3.1.3 - Industrial Policy Enforcement

Forget those `if/else` data checks. Theus v3.1.3 brings Industrial-Grade Audit System backed by Rust with **Active Validation**.

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      TheusEngine (Python)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │   AuditValidator │  │         AuditSystem (Rust)       │ │
│  │   (Python)       │──│   - RingBuffer (Append-Only)     │ │
│  │   - Parse YAML   │  │   - Counters (Per-Key)           │ │
│  │   - Check Rules  │  │   - Levels (S/A/B/C)             │ │
│  │   - Call log_fail│  │   - Dual Thresholds              │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

- **Validator (Python):** Parses `audit_recipe.yaml`, checks rules, calls `log_fail()`.
- **AuditSystem (Rust):** Tracks counts, enforces levels, stores immutable logs.

## 2. Audit Recipe (`audit_recipe.yaml`)

### Structure
```yaml
audit:
  threshold_max: 3        # Global Default: Block after 3 violations
  reset_on_success: true  # Reset counter on successful execution

process_recipes:
  add_product:
    inputs:
      - field: "price"
        min: 0
        level: "B"          # Block if violated
        max_threshold: 1    # Override: Block after 1 fail

    outputs:
      - field: "domain.total_value"
        max: 1000000000
        level: "S"          # Safety Stop
        message: "Danger! Overflow."
```

### Rule Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `field` | string | Path to check (`domain.x`, `input_arg`) |
| `min`, `max` | number | Numeric range validation |
| `min_len`, `max_len` | int | Length validation (lists, strings) |
| `regex` | string | Pattern matching (strings) |
| `level` | S/A/B/C | Override Global Level (see below) |
| `max_threshold` | int | Override Global Threshold |
| `message` | string | Custom error message |

## 3. Audit Levels (S/A/B/C)

| Level | Name | Behavior |
| :---: | :--- | :--- |
| **S** | Stop | Immediate halt. First violation raises `AuditStopError`. |
| **A** | Abort | Abort current operation. Raises `AuditAbortError`. |
| **B** | Block | Block after threshold exceeded. Raises `AuditBlockError`. |
| **C** | Count | Count only. Never blocks. For monitoring. |

## 4. Input Gate & Output Gate

- **Input Gate:** Checks function arguments *before* process executes.
  - *Purpose:* Fail Fast. Don't waste resources.
  - *Hook:* `engine._attempt_execute()` -> `validator.validate_inputs()`.

- **Output Gate:** Checks pending state *after* process runs but *before* commit.
  - *Purpose:* Safety. Don't corrupt state.
  - *Hook:* `engine.execute()` -> `validator.validate_outputs()`.

## 5. Fallback Behavior (CRITICAL)

| Scenario | Behavior |
| :--- | :--- |
| Function NOT in `process_recipes` | **NOT audited** (skipped) |
| Function in spec, NO `inputs` key | Inputs NOT audited, only outputs |
| Function in spec, NO `outputs` key | Outputs NOT audited, only inputs |
| Rule has NO `level` | Uses Global Level (default: Block) |
| Rule has NO `max_threshold` | Uses Global `threshold_max` |
| Global has NO `threshold_max` | Uses **3** (Hardcoded Rust Default) |

> **⚠️ Warning:** If your function is not in `process_recipes`, it runs WITHOUT any audit checks!

## 6. Loading Recipe into Engine

```python
from theus import TheusEngine

# Option 1: File path
engine = TheusEngine(
    context={"domain": {}},
    strict_guards=True,  # Optional: Controls Zone Protection, NOT Audit
    audit_recipe="specs/audit_recipe.yaml"
)

# Option 2: Dict (for testing)
engine = TheusEngine(
    context={"domain": {}},
    strict_guards=False,  # Audit works regardless of this flag!
    audit_recipe={
        "audit": {"threshold_max": 2},
        "process_recipes": {
            "my_func": {
                "inputs": [{"field": "x", "min": 0, "level": "B"}]
            }
        }
    }
)
```

## 7. Rust Classes Reference

```python
from theus_core import (
    AuditSystem,      # Core audit manager
    AuditRecipe,      # Configuration object
    AuditLevel,       # Enum: Stop, Abort, Block, Count
    AuditLogEntry,    # Immutable log record
    AuditBlockError,  # Exception: Threshold exceeded
    AuditAbortError,  # Exception: Operation aborted
    AuditStopError,   # Exception: Immediate halt
    AuditWarning      # Python Warning (Dual Threshold)
)
```

---

**Exercise:**
1. Create `audit.yaml` with rule: `price` must be >= 10 (Level B, max_threshold=1).
2. Run process with price=5. Expect Block on 2nd call.
3. Add rule for `domain.items` with `max_len=5`, level `C`. Run 10 violations. Expect NO block.
