# Chapter 4: TheusEngine - Operating the Machine

> [!CAUTION]
> **OVERHEAD WARNING:** Every call to `await engine.execute()` triggers a **Global Lock** and a **Rust Audit**. Do not call this inside tight loops (e.g. iterating 1M array items). Use Batch Processing instead.

TheusEngine v3.0 is a high-performance Rust machine. Understanding its execution flow makes debugging easier.

## 1. Initializing Standard v3.0 Engine
```python
from theus import TheusEngine
from warehouse_ctx import WarehouseContext, WarehouseConfig, WarehouseDomain

# Setup Context
config = WarehouseConfig(max_capacity=500)
domain = WarehouseDomain()
sys_ctx = WarehouseContext(global_ctx=config, domain=domain)

# Initialize Engine (Strict Guards is default on v3.0, good for Dev)
# Note: strict_cas default is False (Smart Mode)
engine = TheusEngine(sys_ctx, strict_guards=True)
```

## 2. New API in v3.0

> **⚠️ BREAKING CHANGE:** Method names have changed.

| v2.2 | v3.0 | Notes |
|:-----|:-----|:------|
| `engine.register_process(name, func)` | `engine.register(func)` | Name auto-detected |
| `engine.run_process(name, **kwargs)` | `await engine.execute(func_or_name, **kwargs)` | Accepts func or string |

## 2. The Execution Pipeline
When you call `await engine.execute(add_product, product_name="TV", price=500)`, what actually happens?

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
    inputs=['domain.items'],
    outputs=['domain.items', 'domain.total_value']
)
def add_product(ctx, product_name: str, price: int):
    ctx.domain.items.append({"name": product_name, "price": price})
    ctx.domain.total_value += price
    return "Added"

# Register process (v3.0 style)
engine.register(add_product)

try:
    # Execute (v3.0 style) - by function reference
    result = await engine.execute(add_product, product_name="Iphone", price=1000)
    print("Success!", sys_ctx.domain.items)
    
    # OR by name string
    result = await engine.execute("add_product", product_name="Galaxy", price=900)
    
except Exception as e:
    print(f"Failed: {e}")
```

## 4. Semantic Process Types

The `@process` decorator accepts a `semantic` argument to define the execution constraints. Understanding this is critical for writing correct code.

| Semantic | Purpose | Constraints | Behavior |
| :--- | :--- | :--- | :--- |
| **`effect`** (Default) | General Logic | None | Standard read/write access. Protected by Rust Core transaction. |
| **`pure`** | Calculation | **Read-Only** | **Zero Trust:** Cannot modify state. Cannot accept `signal.*` inputs. Returns immutable views. |
| **`guide`** | Orchestration | None | **Future Feature:** Currently behaves like `effect`. Reserved for Workflow Orchestrator v4. |

> **Note:** Functionally, there are only two modes in v3.0: **PURE** (Restricted) and **EFFECT** (Unrestricted). The `guide` type is currently just a marker.

### 🛑 Zero Trust Warning: PURE Processes

When you mark a process as `semantic="pure"`, Theus enforces a **Deep Guard** policy:
1.  **Write Blocked:** You cannot assign values (`ctx.domain.x = 1` -> `ContractViolationError`).
2.  **Immutable Views:** Any list or dictionary you read is returned as a `tuple` or `MappingProxyType`.

```python
@process(inputs=['domain.users'], semantic="pure")
def calculate_stats(ctx):
    # OK: Reading values
    user_count = len(ctx.domain.users)
    
    # CRASH: Attempting to mutate a list
    # ctx.domain.users is a TUPLE, not a list!
    ctx.domain.users.append("New User") # AttributeError: 'tuple' object has no attribute 'append'
    
    return user_count
```

> **Why?** PURE processes are designed to be stateless and parallel-safe. If they could mutate objects by reference, they would break the "One Brain" architecture. Theus proactively converts mutable types to immutable ones to prevent accidental "Ghost Writes".

## 5. Auto-Discovery with scan_and_register()

```python
# Scan directory and register all @process functions automatically
engine.scan_and_register("src/processes")
```

This recursively imports all `.py` files and registers any function with `_pop_contract` attribute.

## 6. Workflow Execution

```python
# Execute YAML workflow using Rust Flux DSL Engine
await engine.execute_workflow("workflows/main_workflow.yaml")
```

See Chapter 11 for Flux DSL workflow syntax.

---
**Exercise:**
Write a `main.py`. Run the process using the new `engine.register()` and `await engine.execute()` methods. Try printing `sys_ctx.domain.sig_restock_needed` after execution to see if the Signal was updated.
