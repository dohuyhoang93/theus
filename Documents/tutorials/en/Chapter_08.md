# Chapter 8: Audit System V2 - Industrial Policy Enforcement

Forget those `if/else` data checks. Theus v2 brings Industrial-Grade Audit System.

## 1. Audit Recipe & RuleSpec
All checking rules are defined in YAML file (Audit Recipe) and loaded into Engine at startup.

### New Rule Structure
A Rule is now much more complex:
- **Condition:** `min`, `max`, `eq`, `neq`, `max_len`, `min_len`.
- **Thresholds:** `min_threshold` (Warning) vs `max_threshold` (Action).
- **Level:** `S`, `A`, `B`, `C`.

## 2. Example `audit_recipe.yaml`
```yaml
process_recipes:
  add_product:
    inputs:
      - field: "price"
        min: 0
        level: "B"  # Block if price negative
        
    outputs:
      - field: "domain.total_value"
        max: 1000000000  # Max 1 billion
        level: "S"       # Safety Stop if exceeded
        message: "Danger! Warehouse value overflow."
        
      - field: "domain.items"
        max_len: 1000
        level: "A"       # Abort process if > 1000 items
        min_threshold: 1 # Warn immediately
        max_threshold: 3 # Block on 3rd consecutive violation
```

## 3. Loading Recipe into Engine
```python
from theus.config import ConfigFactory

# 1. Load Recipe from YAML
recipe = ConfigFactory.load_recipe("audit_recipe.yaml")

# 2. Inject into Engine
engine = TheusEngine(sys_ctx, audit_recipe=recipe)
```

## 4. Input Gate & Output Gate
- **Input Gate:** Checks arguments (`price`, `name`) *before* Process runs. Saves resources (Fail Fast).
- **Output Gate:** Checks Context (`domain.total_value`) *after* Process runs (on Shadow) but *before* Commit.

---
**Exercise:**
Create `audit.yaml`. Configure rule: `price` must be >= 10. `domain.items` max_len = 5.
Run process adding product with price 5 -> See Block at Input Gate.
Run process adding 6th item -> See Abort at Output Gate.
