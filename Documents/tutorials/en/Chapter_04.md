# Chapter 4: TheusEngine - Operating the Machine

TheusEngine v2 is a high-performance Rust machine. Understanding its execution flow makes debugging easier.

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
When you call `engine.run_process("add_product", product_name="TV", price=500)`, what actually happens?

1.  **Audit Input Gate:**
    - Rust calls `AuditPolicy`.
    - Checks if input arguments (`product_name`, `price`) violate any Audit Rules.
    - If `Level S` violation -> **Stop Immediately**.

2.  **Context Locking:**
    - Engine **Locks** the entire Context (Mutex) to ensure Atomic Execution (Thread Safe).

3.  **Transaction Start:**
    - Rust creates a `Transaction` in RAM.

4.  **Guard Injection:**
    - Rust creates a `ContextGuard` wrapping the real Context.
    - Grants permissions (Keys) based on the Process Contract (`inputs`/`outputs`).

5.  **Execution:**
    - Your Python code runs. All changes (`+= price`) happen on the Guard/Transaction logic (Shadow Copy).

6.  **Audit Output Gate:**
    - Process finishes.
    - Rust checks the result. E.g., "After adding, does `total_value` exceed limit?".
    - If violation -> **Rollback Transaction**.

7.  **Commit/Rollback:**
    - If everything OK -> Apply changes to Real Context.
    - Unlock Context.

## 3. Running It
```python
engine.register_process("add_product", add_product)

try:
    # Use 'product_name' to avoid collision with internal 'name' argument
    engine.run_process("add_product", product_name="Iphone", price=1000)
    print("Success!", sys_ctx.domain_ctx.items)
except Exception as e:
    print(f"Failed: {e}")
```

---
**Exercise:**
Write a `main.py`. Run the process. Try printing `sys_ctx.domain_ctx.sig_restock_needed` after execution to see if the Signal was updated.
