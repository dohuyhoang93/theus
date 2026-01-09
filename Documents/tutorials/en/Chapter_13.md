# Chapter 13: Service Layer Pattern (FastAPI Integration)

Theus is designed to be the "Iron Core" Service Layer for modern Web APIs.
This aligns with **Domain-Driven Design (DDD)** and **Clean Architecture**.

## 1. 3-Layer Architecture Setup

Think of your codebase in 3 layers:

1.  **FastAPI (Controller):** Handles HTTP, JSON Parsing, Authentication (User Identity).
2.  **Theus (Service/Model):** Handles Business Logic, Transactionality, Safety Checks.
3.  **Context/DB (Persistence):** Storage.

## 2. The Dependency Injection Pattern
We recommend injecting the `TheusEngine` using FastAPI's Dependency Injection.

### Step 1: `dependencies.py`
```python
from theus.engine import TheusEngine
from my_app.context import SystemContext
from my_app.config import load_recipes

_engine = None

def get_engine() -> TheusEngine:
    global _engine
    if not _engine:
        # Initialize Context & Engine ONCE (Singleton)
        ctx = SystemContext(...)
        recipe = load_recipes("audit.yaml")
        _engine = TheusEngine(ctx, audit_recipe=recipe, strict_mode=True)
    return _engine
```

### Step 2: `main.py` (FastAPI)
```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from theus.engine import TheusEngine
from theus.audit import AuditBlockError, AuditInterlockError
from .dependencies import get_engine

app = FastAPI()

class OrderRequest(BaseModel):
    item_id: str
    quantity: int

@app.post("/orders")
def create_order(req: OrderRequest, engine: TheusEngine = Depends(get_engine)):
    try:
        # 1. Delegate Logic to Theus
        # Note: We pass Pydantic models (req) directly if Process supports it, 
        # or unpack args.
        result = engine.run_process("create_order", item_id=req.item_id, qty=req.quantity)
        
        return {"status": "success", "order_id": result}
        
    except AuditBlockError as e:
        # 2. Map Policy Violations to 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))
        
    except AuditInterlockError as e:
        # 3. Map Safety Violations to 500 or 503
        # (Log critical alert here)
        raise HTTPException(status_code=503, detail="System Safety Interlock Triggered")
```

## 3. Stateless vs Stateful
Web APIs are Stateless. Theus Context is Stateful.
**Strategy: Context Hydration.**

In `create_order` process:
1.  **Read:** Load user data from DB into `ctx.domain_ctx` (if not cached).
2.  **Process:** Logic.
3.  **Write:** Save `ctx.domain_ctx` back to DB.

Ideally, wrap the `engine.run_process` call in a DB Transaction scope to ensure Theus Commit aligns with DB Commit.

---
**Exercise:**
Build a "Bank API".
- Endpoint: `POST /transfer`.
- Theus Process: `transfer_funds`.
- Audit Rule: `balance` cannot be negative (Level B).
- Try sending a request that drains account. Verify you get HTTP 400.
