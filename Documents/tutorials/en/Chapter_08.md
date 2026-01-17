# Chapter 8: Audit System V3 - Industrial Policy Enforcement

Forget those `if/else` data checks. Theus v3.0 brings Industrial-Grade Audit System backed by Rust.

## 1. Audit Recipe & RuleSpec
All checking rules are defined in YAML file (Audit Recipe) and loaded into Engine at startup.

### New Rule Structure
A Rule is now much more complex:
- **Condition:** `min`, `max`, `eq`, `neq`, `max_len`, `min_len`, `regex`.
- **Thresholds:** `min_threshold` (Warning) vs `max_threshold` (Action).
- **Level:** `S`, `A`, `B`, `C`.

## 2. Example `audit_recipe.yaml`

> **⚠️ Note (v3.0):** Paths now use `domain_ctx.*` format.

```yaml
process_recipes:
  add_product:
    inputs:
      - field: "price"
        min: 0
        level: "B"  # Block if price negative
        
    outputs:
      - field: "domain_ctx.total_value"
        max: 1000000000  # Max 1 billion
        level: "S"       # Safety Stop if exceeded
        message: "Danger! Warehouse value overflow."
        
      - field: "domain_ctx.items"
        max_len: 1000
        level: "A"       # Abort process if > 1000 items
        min_threshold: 1 # Warn immediately
        max_threshold: 3 # Block on 3rd consecutive violation
```

## 3. Loading Recipe into Engine

```python
from theus import TheusEngine

# Inject directly into Engine (v3.0 style)
engine = TheusEngine(
    sys_ctx,
    strict_mode=True,
    audit_recipe="specs/audit_recipe.yaml"  # Path or dict
)
```

## 4. Rust Audit Classes (v3.0)

```python
from theus_core import (
    AuditSystem,
    AuditRecipe,
    AuditLevel,
    AuditLogEntry,
    AuditBlockError,
    AuditAbortError,
    AuditStopError
)
```

### AuditLevel Enum

```python
class AuditLevel:
    Stop = 0   # Level S - Emergency stop
    Abort = 1  # Level A - Hard stop workflow
    Block = 2  # Level B - Rollback transaction
    Count = 3  # Level C - Warning only
```

## 5. Input Gate & Output Gate
- **Input Gate:** Checks arguments (`price`, `name`) *before* Process runs. Saves resources (Fail Fast).
- **Output Gate:** Checks Context (`domain_ctx.total_value`) *after* Process runs (on Shadow) but *before* Commit.

---
**Exercise:**
Create `audit.yaml`. Configure rule: `price` must be >= 10. `domain_ctx.items` max_len = 5.
Run process adding product with price 5 -> See Block at Input Gate.
Run process adding 6th item -> See Abort at Output Gate.
