# Chapter 3: Process & Strict Contracts

In Theus v2, `@process` is not just syntax; it is a **Legal Contract** between your code and the Engine.

## 1. Anatomy of a Contract
```python
@process(
    inputs=['domain.items'],          # READ Permission
    outputs=['domain.total_value'],   # WRITE Permission
    errors=['ValueError']             # ALLOWED Errors
)
```

## 2. The Golden Rule: No Input Signals
This is the biggest difference in v2.
**Rule:** You **MUST NOT** declare a `sig_` or `cmd_` variable in `inputs`.
- *Why?* Because a Process must be **Pure Logic**. Its logic should only depend on persistent Data. Signals are transient; if dependent on them, the Process cannot be reliably Replayed.
- *How to handle Signals?* That is the job of the **Workflow Orchestrator** (Chapter 11). A Process should only handle the *result* of a Signal (Data), not the Signal itself.

## 3. Writing Your First Process
```python
from theus.contracts import process

@process(
    inputs=['domain.items'],           # Read-only items
    outputs=[
        'domain.items',                # Write items (append)
        'domain.total_value',          # Write total
        'domain.sig_restock_needed'    # Trigger alarm flag
    ],
    errors=['ValueError']
)
def add_product(ctx, name: str, price: int):
    if price < 0:
        raise ValueError("Price cannot be negative!")
    
    # Business Logic
    product = {"name": name, "price": price}
    
    # ctx.domain.items is now a TrackedList (unlocked because it's in outputs)
    ctx.domain.items.append(product)
    
    # Update total
    ctx.domain.total_value += price
    
    # Trigger Signal if needed (Output Signal is OK!)
    if len(ctx.domain.items) > 100:
        ctx.domain.sig_restock_needed = True
        
    return "Added"
```

## 4. Fail-Fast Mechanism
If you forget to declare `domain.total_value` in `outputs` but try to `+= price`:
Theus v2 will raise `ContractViolationError` immediately. This is **Zero Trust Memory** - trusting no one, not even the coder.

---
**Exercise:**
Write the `add_product` process as above. Try intentionally removing the line `outputs=['domain.total_value']` and run it to see what error occurs.
