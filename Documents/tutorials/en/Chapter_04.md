# Chapter 4: TheusEngine - Operating the Machine

TheusEngine v2 is a complex machine with multiple layers of protection. Understanding its execution flow makes debugging easier.

## 1. Initializing Standard v2 Engine
```python
from theus.engine import TheusEngine
from warehouse_ctx import WarehouseContext, WarehouseConfig, WarehouseDomain

# Setup Context
config = WarehouseConfig(max_capacity=500)
domain = WarehouseDomain()
sys_ctx = WarehouseContext(global_ctx=config, domain_ctx=domain)

# Initialize Engine (Strict Mode is default on v2, good for Dev)
engine = TheusEngine(sys_ctx, strict_mode=True)
```

## 2. The Execution Pipeline
When you call `engine.run_process("add_product", name="TV", price=500)`, what actually happens?

1.  **Audit Input Gate:**
    - Engine calls `ContextAuditor`.
    - Checks if input arguments (`name`, `price`) violate any Audit Rules (if Recipe exists).
    - If `Level S` violation -> **Stop Immediately**.

2.  **Context Locking:**
    - If running multi-threaded, Engine **Locks** the entire Context to ensure Atomic Execution.

3.  **Transaction Start:**
    - Engine snapshots the current state (or prepares Shadow Copy mechanism).

4.  **Guard Injection:**
    - Engine creates a `ContextGuard` wrapping the real Context.
    - Grants permissions (Keys) based on the Process Contract.

5.  **Execution:**
    - Your code runs. All changes happen on the Draft (Shadow/Delta).

6.  **Audit Output Gate:**
    - Process finishes, but not Committed yet.
    - Engine checks the result on the Draft. E.g., "After adding, does `total_value` exceed 1 billion?".
    - If violation -> **Rollback**.

7.  **Commit/Rollback:**
    - If everything OK -> Apply Draft to Real Context (Commit).
    - Unlock Context.

## 3. Running It
```python
engine.register_process("add_product", add_product)

try:
    engine.run_process("add_product", name="Iphone", price=1000)
    print("Success!", sys_ctx.domain.items)
except Exception as e:
    print(f"Failed: {e}")
```

---
**Exercise:**
Write a `main.py`. Run the process. Try printing `sys_ctx.domain.sig_restock_needed` after execution to see if the Signal was updated.
