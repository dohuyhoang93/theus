# Module 03: Engine and Transactions

> **For AI Assistants:** TheusEngine is the orchestration core. Understand its API to properly initialize and execute processes.

---

## 1. TheusEngine Overview

```python
from theus import TheusEngine

class TheusEngine:
    def __init__(self, context=None, strict_mode=True, audit_recipe=None):
        """
        Initialize Theus Engine.
        
        Args:
            context: SystemContext instance
            strict_mode: Enable Zero-Trust Memory (default: True)
            audit_recipe: Path to audit YAML or dict
        """
```

### Initialization Pattern

```python
from theus import TheusEngine
from my_context import MySystemContext

# 1. Create context
sys_ctx = MySystemContext()

# 2. Initialize engine
engine = TheusEngine(
    context=sys_ctx,
    strict_mode=True,  # Production: True, Training: False
    audit_recipe="specs/audit_recipe.yaml"  # Optional
)
```

---

## 2. strict_mode Explained

| Mode | Value | Use Case | Behavior |
|:-----|:------|:---------|:---------|
| **Production** | `True` | Deployment | Full transaction, rollback, audit |
| **Training** | `False` | ML training loops | Disabled transactions, max speed |

```python
# Production (Safe)
engine = TheusEngine(sys_ctx, strict_mode=True)

# Training (Fast)
engine = TheusEngine(sys_ctx, strict_mode=False)
```

> **AI Rule:** Default to `strict_mode=True`. Only use `False` for pure training loops where data safety is not critical.

---

## 3. Process Registration

### Method: register()

```python
from theus.contracts import process

@process(inputs=['domain_ctx.x'], outputs=['domain_ctx.y'])
def my_process(ctx):
    # Pure Logic: Read -> Compute -> Return
    new_y = ctx.domain_ctx.x * 2
    return new_y

# Register single process
engine.register(my_process)
```

### Auto-Discovery: scan_and_register()

```python
# Scan directory and register all @process functions
engine.scan_and_register("src/processes")
```

This recursively imports all `.py` files and registers any function with `_pop_contract` attribute.

---

## 4. Process Execution

### Method: execute()

```python
# By function reference
import asyncio
result = await engine.execute(my_process, x=10, y=20)

# By name (string)
result = await engine.execute("my_process", x=10, y=20)
```

### Execution Pipeline

When you call `await engine.execute()`:

```
1. [AUDIT INPUT GATE]
   └─ Check arguments against audit rules
   └─ If Level S violation → STOP
   
2. [CONTEXT LOCKING]
   └─ Mutex lock for thread safety
   
3. [TRANSACTION START]
   └─ Create shadow copy for rollback
   
4. [GUARD INJECTION]
   └─ Create ContextGuard with permissions from contract
   
5. [EXECUTION]
   └─ Run your Python code (Snapshot Isolation)
   └─ Process returns new data (No In-Place Write)
   
6. [AUDIT OUTPUT GATE]
   └─ Check results against audit rules
   └─ If violation → ROLLBACK
   
7. [COMMIT/ROLLBACK]
   └─ Success → Apply changes to real context
   └─ Failure → Discard shadow copy
   
8. [UNLOCK]
   └─ Release mutex
```

---

## 5. Transaction Context Manager

For manual transaction control:

```python
with engine.transaction() as tx:
    # Operations here are transactional
    tx.update(data={'counter': 10})
    
# Auto-commit on success, auto-rollback on exception
```

---

## 6. Safe Edit Pattern

For setup/testing when you need to bypass strict mode temporarily:

```python
# ❌ WRONG - Will raise ContextLockedError
sys_ctx.domain.counter = 0

# ✅ CORRECT - Use edit() context manager
with engine.edit() as ctx:
    ctx.domain.counter = 0
    ctx.domain.items = []
# Auto-relocked after block
```

> **AI Rule:** Use `engine.edit()` ONLY for:
> - Initial data setup
> - Unit test fixtures
> - NEVER in production code

---

## 7. Workflow Execution

### execute_workflow()

```python
# Execute YAML workflow using Rust Flux DSL Engine
# Note: This is synchronous (blocking)
engine.execute_workflow("workflows/main_workflow.yaml")
```

See [04_WORKFLOW_FLUX_DSL.md](./04_WORKFLOW_FLUX_DSL.md) for workflow syntax.

---

## 8. State Access

### Property: state

```python
# Get current engine state (Rust State object)
state = engine.state

# Access data
current_data = state.data
heavy_data = state.heavy
version = state.version
```

---

## 9. Compare-and-Swap Pattern

For optimistic concurrency control:

```python
# Get current version
current_version = engine.state.version

# Perform optimistic update
try:
    engine.compare_and_swap(
        expected_version=current_version,
        data={'counter': new_value}
    )
except VersionMismatchError:
    # Someone else modified state, retry
    pass
```

---

## 10. Error Handling Pattern

```python
from theus import TheusEngine, ContractViolationError
from theus.engine import TransactionError, SecurityViolationError

try:
    result = await engine.execute(my_process, x=10)
    
except ContractViolationError as e:
    # Process violated its contract
    print(f"Contract violation: {e}")
    
except SecurityViolationError as e:
    # Illegal read/write attempt
    print(f"Security violation: {e}")
    
except TransactionError as e:
    # Transaction failed (conflict, timeout)
    print(f"Transaction error: {e}")
```

---

## 11. Async Process Execution

```python
import asyncio
from theus.contracts import process

@process(inputs=['domain.query'], outputs=['domain.result'])
async def async_process(ctx):
    await asyncio.sleep(0.1)
    # Return result directly
    return "done"

# Execute async process
async def main():
    engine = TheusEngine(sys_ctx)
    engine.register(async_process)
    
    result = await engine.execute(async_process, query="test")

asyncio.run(main())
```

---

## 12. AI Implementation Checklist

When generating TheusEngine code:

- [ ] Import: `from theus import TheusEngine`
- [ ] Create SystemContext before Engine
- [ ] Default `strict_mode=True` for production
- [ ] Use `engine.register()` for each process
- [ ] Use `engine.execute()` to run processes
- [ ] Wrap in try/except for error handling
- [ ] Use `engine.edit()` only for setup/testing
- [ ] Use `async/await` for async processes

---

*Next: [04_WORKFLOW_FLUX_DSL.md](./04_WORKFLOW_FLUX_DSL.md)*
