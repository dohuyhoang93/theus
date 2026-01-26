# Chapter 4: TheusEngine - Operating the Machine

> [!CAUTION]
> **OVERHEAD WARNING:** Every call to `engine.execute()` triggers a **Global Lock** and a **Rust Audit**. Do not call this inside tight loops (e.g. iterating 1M array items). Use Batch Processing instead.

TheusEngine v3.0 is a high-performance Rust machine. Understanding its execution flow makes debugging easier.

## 1. Initializing Standard v3.0 Engine
```python
from theus import TheusEngine
from warehouse_ctx import WarehouseContext, WarehouseConfig, WarehouseDomain

# Setup Context
config = WarehouseConfig(max_capacity=500)
domain = WarehouseDomain()
sys_ctx = WarehouseContext(global_ctx=config, domain_ctx=domain)

# Initialize Engine (Strict Mode is default on v3.0, good for Dev)
engine = TheusEngine(sys_ctx, strict_mode=True)
```

## 2. New API in v3.0

> **⚠️ BREAKING CHANGE:** Method names have changed.

| v2.2 | v3.0 | Notes |
|:-----|:-----|:------|
| `engine.register_process(name, func)` | `engine.register(func)` | Name auto-detected |
| `engine.run_process(name, **kwargs)` | `engine.execute(func_or_name, **kwargs)` | Accepts func or string |

## 2. The Execution Pipeline
When you call `engine.execute(add_product, product_name="TV", price=500)`, what actually happens?

1.  **Preparation (Contract Check):**
    - Python Engine verifies the Process Contract.
    - Binds arguments and prepares the Execution Environment.

2.  **Snapshot Isolation:**
    - Rust creates a **Transactional Snapshot** of the state (MVCC).
    - Readers are NOT blocked. Writers work on a local copy.

3.  **Transaction Start:**
    - Rust creates a `Transaction` container to track all changes.

4.  **Guard Injection:**
    - Rust creates a `ContextGuard` wrapping the Snapshot.
    - Grants permissions based on Process Contract (`inputs`/`outputs`).

5.  **Execution:**
    - Your Python code runs. All changes (`+= price`) happen on the Guard/Shadow Copy.

6.  **Audit & Verification:**
    - Process finishes.
    - Checks if outputs match the Contract.
    - Logs success/failure to Audit System.
    > **Tip:** Inspect logs via `engine._audit.get_logs()` if configured.

7.  **Commit (CAS):**
    - Optimistic Commit: Touched keys are checked for conflicts.
    - If Conflict -> Retry (Backoff).
    - If Safe -> Apply changes to Real Context.

> **🧠 Philosophy Note:** Theus pipelines are "Guilty until Proven Innocent". Every step is locked, guarded, and audited. This adheres to Principle 4.2: **"Every Step is Auditable"**. We trade Raw Speed for Absolute Reproducibility. See [POP Manifesto](../../POP_Manifesto.md).

## 3. Running It
```python
from theus.contracts import process

@process(
    inputs=['domain_ctx.items'],
    outputs=['domain_ctx.items', 'domain_ctx.total_value']
)
def add_product(ctx, product_name: str, price: int):
    ctx.domain_ctx.items.append({"name": product_name, "price": price})
    ctx.domain_ctx.total_value += price
    return "Added"

# Register process (v3.0 style)
engine.register(add_product)

try:
    # Execute (v3.0 style) - by function reference
    result = engine.execute(add_product, product_name="Iphone", price=1000)
    print("Success!", sys_ctx.domain_ctx.items)
    
    # OR by name string
    result = engine.execute("add_product", product_name="Galaxy", price=900)
    
except Exception as e:
    print(f"Failed: {e}")
```

## 5. Auto-Discovery with scan_and_register()

```python
# Scan directory and register all @process functions automatically
engine.scan_and_register("src/processes")
```

This recursively imports all `.py` files and registers any function with `_pop_contract` attribute.

## 6. Workflow Execution

```python
# Execute YAML workflow using Rust Flux DSL Engine
engine.execute_workflow("workflows/main_workflow.yaml")
```

See Chapter 11 for Flux DSL workflow syntax.

---
**Exercise:**
Write a `main.py`. Run the process using the new `engine.register()` and `engine.execute()` methods. Try printing `sys_ctx.domain_ctx.sig_restock_needed` after execution to see if the Signal was updated.
