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
            strict_mode: Enable strict architectural guards (default: True)
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
| **Production** | `True` | Deployment | Full architectural safety, Private access blocked |
| **Research/Hack** | `False` | Debugging/Experiments | Disables limits/checks (e.g. private attrs), but Transactions still active |

```python
# Production (Safe)
engine = TheusEngine(sys_ctx, strict_mode=True)

# Training (Fast)
engine = TheusEngine(sys_ctx, strict_mode=False)
```

> **AI Rule:** Default to `strict_mode=True`. Use `False` only for debugging or when you need to bypass architectural constraints (e.g. access private `_` attributes).

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

## 9. Compare-And-Swap (CAS) Pattern

Theus v3 provides two CAS modes for optimistic concurrency control:

### 9.1 Configuration

```python
# Initialize Engine with desired CAS mode
engine = TheusEngine(
    context=sys_ctx,
    strict_cas=False  # Default: Smart CAS (Field-Level Tracking)
    # strict_cas=True   # Option: Strict CAS (Version-Level Rejection)
)
```

### 9.2 API Usage

```python
# 1. Get current version
current_version = engine.state.version

# 2. Perform optimistic update
try:
    # If strict_cas=False (default), this SUCCEEDS if:
    # - exact version match OR
    # - only unrelated fields have changed (Field-Level Merge)
    engine.compare_and_swap(
        expected_version=current_version,
        data={'counter': new_value}
    )
except VersionMismatchError:
    # Genuine conflict detected (same field modified)
    # Retry logic needed
    pass

# If strict_cas=True, this fails on ANY version mismatch.
```

### 9.3 4-Tier Case Analysis

How different APIs behave under various conditions:

| Case | Scenario | Strict CAS (Python) | Smart CAS (Rust) | Transaction (`tx.update`) |
| :--- | :--- | :--- | :--- | :--- |
| **1. Standard** | Single thread, version match | ✅ Success | ✅ Success | ✅ Auto-commit |
| **2. Related** | Multi-field update | ✅ Success (Version based) | ✅ Success (Field based) | ✅ Batched commit |
| **3. Edge** | Stale version, diff fields | ❌ **Reject** (Ver mismatch) | ✅ **SUCCESS** (Partial Merge) | N/A (No checks) |
| **4. Conflict** | Stale version, same field | ❌ Reject | ❌ Reject (ContextError) | ⏳ Blocked (Mutex) |

### 9.4 Decision Guide

| API | Use Case |
| :--- | :--- |
| `engine.compare_and_swap(strict_cas=True)` | **Banking/Audit**: World state must be exact. |
| `engine.compare_and_swap(strict_cas=False)` | **High Concurrency**: Allow non-conflicting merges. |
| `engine.transaction().update()` | **Complex Logic**: Sequential consistency via locking. |

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

## 12. State Mutation Strategy (Decision Tree)

When implementing a User Request, use this logic to choose the right API:

```
IF (Request is "Business Logic" OR "Processing Data"):
    -> USE Implicit POP (@process)
    -> "Just return the new data in the function."

ELSE IF (Request is "Initialization" OR "Setup"):
    -> USE Batch Transaction (engine.transaction)
    -> "Batch updates together at startup."

ELSE IF (Request is "Testing" OR "Debug"):
    -> USE Safe Edit (engine.edit)
    -> "Modify state directly (Bypasses guards, Use with Caution)."

ELSE IF (Request is "Lock", "Mutex", or "High Concurrency Counter"):
    -> USE Explicit CAS (compare_and_swap)
        IF (System requires Absolute Safety like Banking):
            -> Strict CAS (strict_cas=True)
        ELSE (System requires Throughput):
            -> Smart CAS (strict_cas=False)

ELSE:
    -> REJECT or Ask for Clarification.
```

---

## 13. AI Implementation Checklist

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
