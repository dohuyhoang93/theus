# 09_AUDIT_SYSTEM_INTERNALS.md

**Status:** Active (3.0.22)
**Component:** `theus_core` (Rust) + `theus.validator` (Python)

## Overview
This document specifies the internal workings of the Active Audit Validator deployed in Theus v3.1.3. It covers the two-layer architecture (Python Validator + Rust AuditSystem), granular level overrides, and fallback behaviors.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         TheusEngine                             │
│  ┌──────────────┐     ┌───────────────────────────────────────┐ │
│  │ _attempt_exe │ ──▶ │ AuditValidator.validate_inputs()      │ │
│  │       ↓      │     │   - Parse rule from definitions       │ │
│  │  [Process]   │     │   - Check min/max/regex/len           │ │
│  │       ↓      │     │   - On Violation:                     │ │
│  │   commit()   │ ──▶ │       log_fail(key, level?, thresh?)  │ │
│  └──────────────┘     └───────────────────────────────────────┘ │
│                                    │                            │
│                                    ▼                            │
│                       ┌────────────────────────┐                │
│                       │   AuditSystem (Rust)   │                │
│                       │   - RingBuffer (1000)  │                │
│                       │   - HashMap<key, u32>  │                │
│                       │   - log_fail() logic   │                │
│                       └────────────────────────┘                │
└────────────────────────────────────────────────────────────────┘
```

## Data Structures

### `AuditRecipe` (Rust)
```rust
#[pyclass]
struct AuditRecipe {
    level: AuditLevel,       // Global default
    threshold_max: u32,      // Global max (default: 3)
    threshold_min: u32,      // Warning threshold
    reset_on_success: bool,  // Reset counters on success
}
```

### `AuditValidator` (Python)
```python
class AuditValidator:
    def __init__(self, definitions: Dict, audit_system: AuditSystem):
        self.definitions = definitions  # From process_recipes
        self.audit_system = audit_system
```

## Algorithms

### 1. `validate_inputs(func_name, kwargs)`
```
FOR each rule in definitions[func_name]["inputs"]:
    value = kwargs.get(rule.field)
    IF check_rule(value, rule) FAILS:
        level_override = map_level(rule.level)  # S/A/B/C -> Enum
        thresh_override = rule.max_threshold
        audit_system.log_fail(key, level=level_override, threshold_max=thresh_override)
```

### 2. `log_fail(key, level?, threshold_max?)` (Rust)
```rust
fn log_fail(&mut self, key, level, threshold_max) {
    count = self.counts[key] += 1
    
    effective_level = level.unwrap_or(self.recipe.level)
    effective_thresh = threshold_max.unwrap_or(self.recipe.threshold_max)
    
    match effective_level {
        Stop  => raise AuditStopError immediately
        Abort => raise AuditAbortError immediately
        Block => if count > effective_thresh { raise AuditBlockError }
        Count => // do nothing, just count
    }
}
```

## Fallback Priority

| Check | Priority | Source |
| :--- | :---: | :--- |
| Level | 1 | Rule `level` field |
| Level | 2 | Global `audit.level` (if exists) |
| Level | 3 | Rust Default: `Block` |
| Threshold | 1 | Rule `max_threshold` field |
| Threshold | 2 | Global `audit.threshold_max` |
| Threshold | 3 | Rust Default: `3` |

## Skip Conditions

| Condition | Result |
| :--- | :--- |
| `func_name` not in `process_recipes` | Skip all validation |
| No `inputs` key in recipe | Skip input validation |
| No `outputs` key in recipe | Skip output validation |
| `field` not in `kwargs` | Skip that rule |
| `value` is `None` after path resolution | Skip that rule |

## Independence from `strict_guards`

> **IMPORTANT:** Audit is **completely independent** of the `strict_guards` flag.

| `strict_guards` | Audit | Zone Protection | Private Attr Block |
| :---: | :---: | :---: | :---: |
| `True` | ✅ Active | ✅ Active | ✅ Active |
| `False` | ✅ Active | ❌ Disabled | ❌ Disabled |

**Verified by:** `tests/03_audit/verify_real_spec_flow.py` (TEST 4)

## Exception Hierarchy

```
BaseException
├── AuditStopError   (Level S - Critical Safety)
├── AuditAbortError  (Level A - Operation Cancel)
└── AuditBlockError  (Level B - Threshold Exceeded)
```

## Logging (RingBuffer)

All events (success/fail) are logged to an append-only RingBuffer:
- **Capacity:** 1000 entries (configurable).
- **Thread Safety:** `Arc<Mutex<RingBuffer>>`.
- **Immutability:** Entries cannot be modified after creation.

```python
# Access logs
logs = engine.audit_system.get_logs()
for entry in logs:
    print(f"{entry.timestamp}: {entry.key} - {entry.message}")
```
