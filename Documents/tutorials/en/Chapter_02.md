# Chapter 2: Designing the 3-Axis Context

In Theus v2, the Context is not just a bag of data. It is a 3-dimensional structure that helps the Engine understand and protect your data.

## 1. The "Hybrid Context Zones" Mindset
Instead of forcing you to write `ctx.domain.data.user_id` (too verbose), Theus v2 uses a **Hybrid** mechanism. You write it flat (`ctx.domain.user_id`), but the Engine implicitly classifies it into **Zones** based on Naming Conventions or Schema.

| Zone | Prefix | Nature | Protection Mechanism |
| :--- | :--- | :--- | :--- |
| **DATA** | (None) | Business Asset. Persistent. | Full Transaction, Strict Replay. |
| **SIGNAL** | `sig_`, `cmd_` | Event/Command. Transient. | Transaction Reset, No Replay. |
| **META** | `meta_` | Debug Info. | Read-only (usually). |

## 2. Design with Dataclasses
We still use `dataclass`, but we must adhere to Zone conventions.

```python
from dataclasses import dataclass, field
from theus.context import BaseSystemContext

# 1. Define Domain (Business Logic)
@dataclass
class WarehouseDomain(BaseDomainContext):
    # --- DATA ZONE (Assets) ---
    items: list = field(default_factory=list)
    total_value: int = 0
    
    # --- SIGNAL ZONE (Control) ---
    sig_restock_needed: bool = False  # Flag indicating restock needed
    cmd_stop_robot: bool = False      # Emergency stop command

# 2. Define Global (Configuration)
@dataclass
class WarehouseConfig(BaseGlobalContext):
    max_capacity: int = 1000
    warehouse_name: str = "Main Warehouse"

# 3. Attach to System Context
@dataclass
class WarehouseContext(BaseSystemContext):
    # BaseSystemContext requires 'domain_ctx' and 'global_ctx'
    # We enforce type hinting for clarity
    domain_ctx: WarehouseDomain = field(default_factory=WarehouseDomain)
    global_ctx: WarehouseConfig = field(default_factory=WarehouseConfig)
```

## 3. Why is Zoning Important?
When you run a **Replay (Bug Reproduction)**:
- Theus will restore exactly `items` and `total_value` (Data Zone).
- Theus will **IGNORE** `sig_restock_needed` (Signal Zone) because it is past noise.
This ensures **Determinism** - Running 100 times yields the exact same result.

## 4. Locked Context Mechanism
Theus protects the Context using `LockManager` (enforced by Rust Core).

### 4.1. Default State: LOCKED
As soon as you initialize `Engine(ctx, strict_mode=True)`, the Context switches to a **LOCKED** state.
If you try to modify it externally (External Mutation):
```python
# Code outside of @process
def hack_system(ctx):
    # This will FAIL if strict_mode=True
    ctx.domain.total_value = 9999 # -> Raises ContextLockedError!
```
The system raises an error to prevent Untraceable Mutations.

> **Note:** `strict_mode=True` is Highly Recommended for Production/Testing to guarantee data integrity.

### 4.2. Valid Mutation: `engine.edit()`
In special cases (like Unit Tests, Initial Data Setup), you need to modify the Context without writing a Process. Theus provides a "Master Key":

```python
# Temporarily unlock within the with block
with engine.edit() as safe_ctx:
    safe_ctx.domain.total_value = 100
    safe_ctx.domain.items.append("Setup Item")
# Exit block -> Automatically RELOCKED immediately.
```

---
**Exercise:**
Create a file `warehouse_ctx.py`. Define the Context as above.
Try writing a main function, initialize the Engine, then intentionally assign `ctx.domain.total_value = 1` without using `engine.edit()`. Observe the `ContextLockedError`.
