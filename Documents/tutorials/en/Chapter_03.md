# Chapter 3: Process & Strict Contracts

In Theus v3.0, `@process` is not just syntax; it is a **Legal Contract** between your code and the Engine.

## 1. Anatomy of a Contract
```python
from theus.contracts import process, SemanticType

@process(
    inputs=['domain_ctx.items'],          # READ Permission
    outputs=['domain_ctx.total_value'],   # WRITE Permission
    errors=['ValueError'],                # ALLOWED Errors
    semantic=SemanticType.EFFECT          # Process classification
)
def my_process(ctx, ...):
    ...
```

### 📐 Visual Contract

```text
       (Read-Only)               (Pure Logic)               (Write-Only)
      +-----------+           +----------------+           +------------+
      |  INPUTS   | --------> |    PROCESS     | --------> |  OUTPUTS   |
      | (Frozen)  |           |   (Function)   |           | (Mutation) |
      +-----------+           +----------------+           +------------+
            ^                         |                          |
            |                         v                          v
      [Audit Gate]               [Exception]                [Commit]
     (Check Rules)             (Rollback All)            (Append Log)
```

## 2. Critical Path Change in v3.0

> **⚠️ BREAKING CHANGE:** Contract paths now use `domain_ctx` instead of `domain`.

```python
# ❌ OLD (v2.2) - Will fail in v3.0
@process(inputs=['domain.items'])

# ✅ NEW (v3.0) - Correct
@process(inputs=['domain_ctx.items'])
```

The Rust Core now performs strict path validation and will reject legacy paths.

## 3. The Golden Rule: No Input Signals
This is the biggest difference in v3.0.
**Rule:** You **MUST NOT** declare a `sig_` or `cmd_` variable in `inputs`.
- *Why?* Because a Process must be **Pure Logic**. Its logic should only depend on persistent Data. Signals are transient; if dependent on them, the Process cannot be reliably Replayed.
- *How to handle Signals?* That is the job of the **Flux DSL** (Chapter 11). A Process should only handle the *result* of a Signal (Data), not the Signal itself.

> **🧠 Philosophy Note:** This enforces **Determinism**. Signals are "Time-Dependent" (Ephemeral), while Data is "State-Dependent" (Persistent). Mixing them breaks the ability to Replay history. See Principle 2.3 of the [POP Manifesto](../../POP_Manifesto.md).

## 4. Semantic Types

```python
from theus.contracts import SemanticType

class SemanticType(Enum):
    PURE = "pure"      # No side effects, deterministic
    EFFECT = "effect"  # May have side effects (default)
    GUIDE = "guide"    # Orchestration/coordination
```

## 5. Writing Your First Process
```python
from theus.contracts import process

@process(
    inputs=['domain_ctx.items'],           # Read-only items (FrozenList)
    outputs=[
        'domain_ctx.items',                # Write items (append)
        'domain_ctx.total_value',          # Write total
        'domain_ctx.sig_restock_needed'    # Trigger alarm flag
    ],
    errors=['ValueError']
)
def add_product(ctx, product_name: str, price: int):
    if price < 0:
        raise ValueError("Price cannot be negative!")
    
    # Business Logic
    product = {"name": product_name, "price": price}
    
    # ctx.domain_ctx.items is now a TrackedList (unlocked because it's in outputs)
    ctx.domain_ctx.items.append(product)
    
    # Update total
    ctx.domain_ctx.total_value += price
    
    # Trigger Signal if needed (Output Signal is OK!)
    if len(ctx.domain_ctx.items) > 100:
        ctx.domain_ctx.sig_restock_needed = True
        
    return "Added"
```

## 6. Async Process Pattern

```python
import asyncio
from theus.contracts import process

@process(
    inputs=['domain_ctx.query'],
    outputs=['domain_ctx.result']
)
async def fetch_data(ctx):
    """Async process for I/O operations."""
    query = ctx.domain_ctx.query
    
    # Async I/O
    await asyncio.sleep(0.1)  # Simulated API call
    result = {"data": f"Result for {query}"}
    
    ctx.domain_ctx.result = result
    return result
```

## 7. Fail-Fast Mechanism
If you forget to declare `domain_ctx.total_value` in `outputs` but try to `+= price`:
Theus v3.0 will raise `ContractViolationError` immediately via the Rust Guard. This is **Zero Trust Memory** - trusting no one, not even the coder.

---
**Exercise:**
Write the `add_product` process as above. Try intentionally removing the line `outputs=['domain_ctx.total_value']` and run it to see what error occurs.
