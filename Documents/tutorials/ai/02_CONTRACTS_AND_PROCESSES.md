# Module 02: Contracts and Processes

> **For AI Assistants:** The `@process` decorator is the core of Theus. Every function that touches Context MUST use it.

---

## 1. The Process Contract

A Process Contract is a **legal agreement** between your code and the Theus Engine.

### Contract Declaration

```python
from theus.contracts import process, SemanticType

@process(
    inputs=['domain_ctx.items', 'global_ctx.max_limit'],
    outputs=['domain_ctx.items', 'domain_ctx.counter'],
    errors=['ValueError', 'KeyError'],
    semantic=SemanticType.EFFECT,
    side_effects=['http_request']
)
def my_process(ctx, ...):
    ...
```

### Contract Parameters

| Parameter | Type | Required | Purpose |
|:----------|:-----|:---------|:--------|
| `inputs` | `List[str]` | No | Paths with READ permission |
| `outputs` | `List[str]` | No | Paths with WRITE permission |
| `errors` | `List[str]` | No | Allowed exception types |
| `semantic` | `SemanticType` | No | Process classification |
| `side_effects` | `List[str]` | No | External effects (logging) |

---

## 2. Path Syntax

### Critical Rule: Use `domain_ctx` NOT `domain`

```python
# ✅ CORRECT
inputs=['domain_ctx.user.name']

# ❌ WRONG - Rust Core will reject
inputs=['domain.user.name']
```

### Path Examples

| Access Pattern | Contract Path |
|:---------------|:--------------|
| `ctx.domain.items` | `'domain.items'` |
| `ctx.domain.user.name` | `'domain.user.name'` |
| `ctx.global_.max_limit` | `'global.max_limit'` |
| `ctx.domain.sig_alert` | `'domain.sig_alert'` |

### Parent Path Inheritance

Declaring a parent path grants access to all children:

```python
# Grants access to user.name, user.email, user.age, etc.
inputs=['domain.user']
```

---

## 3. SemanticType Classification

```python
from theus.contracts import SemanticType

class SemanticType(Enum):
    PURE = "pure"      # No side effects, deterministic
    EFFECT = "effect"  # May have side effects (default)
    GUIDE = "guide"    # Orchestration/coordination process
```

| Type | Use When | Example |
|:-----|:---------|:--------|
| `PURE` | Math, validation, transformation | `calculate_total()` |
| `EFFECT` | Database, API calls, mutations | `save_user()` |
| `GUIDE` | Workflow coordination | `decide_next_step()` |

---

## 4. Complete Process Pattern

```python
from theus.contracts import process, SemanticType

@process(
    inputs=[
        'domain.cart_items',
        'domain.user_id',
        'global.tax_rate'
    ],
    outputs=[
        'domain.cart_items',
        'domain.total_price',
        'domain.sig_checkout_ready'
    ],
    errors=['ValueError']
)
def calculate_cart_total(ctx):
    """
    Calculate total price with tax.
    
    Inputs:
        - cart_items: List of {name, price, quantity}
        - user_id: For audit logging
        - tax_rate: From global config
    
    Outputs:
        - cart_items: (unchanged, but declared for consistency)
        - total_price: Calculated sum with tax
        - sig_checkout_ready: Signal when total > 0
    """
    # 1. Read inputs (immutable)
    items = ctx.domain.cart_items
    tax_rate = ctx.global_.tax_rate
    
    # 2. Validation
    if not items:
        raise ValueError("Cart is empty")
    
    # 3. Business logic
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    total = subtotal * (1 + tax_rate)
    final_total = round(total, 2)
    
    # 4. Determine Signal
    checkout_ready = False
    if total > 0:
        checkout_ready = True
    
    # 5. Return Outputs
    # Must match sequence: outputs=[cart_items, total_price, sig_checkout_ready]
    # Note: cart_items unchanged, so we return original (Engine optimizes this No-Op)
    return items, final_total, checkout_ready
```

---

## 5. Async Process Pattern

```python
import asyncio
from theus.contracts import process

@process(
    inputs=['domain.query'],
    outputs=['domain.result']
)
async def fetch_data(ctx):
    """Async process for I/O operations."""
    query = ctx.domain.query
    
    # Async I/O
    await asyncio.sleep(0.1)  # Simulated API call
    result = {"data": f"Result for {query}"}
    
    # Return result directly (Mapped to outputs=['domain.result'])
    return result
```

---

## 6. Contract Violations

### Violation Types

| Violation | Exception | Cause |
|:----------|:----------|:------|
| Read undeclared | `PermissionError: Illegal Read` | Accessing path not in `inputs` |
| Write undeclared | `PermissionError: Illegal Write` | Writing path not in `outputs` |
| Write to input | `ContractViolationError` | Path in `inputs` but trying to write |

### Example Violations

```python
@process(inputs=['domain.items'])  # No outputs declared!
def broken_process(ctx):
    ctx.domain.items.append("new")  # ❌ ContractViolationError
    ctx.domain.counter += 1          # ❌ PermissionError: Illegal Write
```

### Fix

```python
@process(
    inputs=['domain.items'],
    outputs=['domain.items', 'domain.counter']  # ✅ Declared
)
def fixed_process(ctx):
    ctx.domain.items.append("new")  # ✅ OK
    ctx.domain.counter += 1          # ✅ OK
```

---

## 7. The Golden Rule: No Input Signals

```python
# ❌ WRONG - Signals should NOT be inputs
@process(inputs=['domain.sig_start'])
def bad_process(ctx):
    if ctx.domain.sig_start:
        ...

# ✅ CORRECT - Handle signals in Flux DSL workflow
# workflow.yaml:
# - flux: if
#     condition: "domain['sig_start'] == True"
#     then:
#       - "good_process"
```

**Why?** Signals are transient (time-dependent). Processes must be deterministic (state-dependent) for replay.

---

## 8. Bare Decorator Usage

For simple processes, you can use `@process` without arguments:

```python
@process  # Equivalent to @process(inputs=[], outputs=[])
def read_only_process(ctx):
    # Can only read, cannot write
    print(ctx.domain_ctx.items)  # Will fail in strict mode
```

> **AI Note:** Always prefer explicit `inputs`/`outputs` for clarity.

---

## 9. AI Implementation Checklist

When generating `@process` code:

- [ ] Import: `from theus.contracts import process, SemanticType`
- [ ] Declare ALL read paths in `inputs`
- [ ] Declare ALL write paths in `outputs`
- [ ] Use `domain_ctx` not `domain` in paths
- [ ] Add parent path if accessing nested fields
- [ ] Declare allowed exceptions in `errors`
- [ ] Use `async def` for I/O-bound operations
- [ ] NEVER put signals in `inputs`
- [ ] Return meaningful result for debugging

---

*Next: [03_ENGINE_AND_TRANSACTIONS.md](./03_ENGINE_AND_TRANSACTIONS.md)*
