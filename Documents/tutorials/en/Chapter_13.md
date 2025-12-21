# Chapter 13: Web Integration - Theus as a Service

Theus is designed to be the robust Backend Service for modern Web/APIs.

## 1. 3-Layer Architecture (Clean Architecture)

- **Layer 1: Controller (FastAPI/Flask)**
    - Receive HTTP Request.
    - Basic JSON validation (Pydantic).
    - Call Theus Engine.

- **Layer 2: Service (Theus Engine)**
    - **Input Gate:** Complex Business Validation.
    - **Transaction:** Ensure Integrity.
    - **Process:** Execute Logic.

- **Layer 3: Persistence (Database)**
    - Save Context to DB (Snapshot).

## 2. Dependency Injection (FastAPI)
```python
from fastapi import FastAPI, Depends
from theus.engine import TheusEngine

app = FastAPI()

# Singleton Engine (or Per-Request depending on strategy)
_engine = None
def get_engine():
    global _engine
    if not _engine:
        # Init Engine, Load Recipes...
        _engine = TheusEngine(...) 
    return _engine

@app.post("/order")
def create_order(item_id: str, engine: TheusEngine = Depends(get_engine)):
    try:
        # Call Process. All business logic is inside Theus.
        # Controller is just a courier.
        result = engine.run_process("create_order", item_id=item_id)
        return {"status": "success", "order": result}
        
    except AuditInterlockError as e:
        # Map Theus error to HTTP 400/500
        return {"error": "Policy Violation", "detail": str(e)}, 400
```

## 3. Stateless HTTP vs Stateful Context
HTTP is Stateless. Theus Context is Stateful.
How to combine?
- **Hydration:** At start of Request, load Context from DB (by SessionID/UserID) into Theus.
- **Run:** Run Theus Process.
- **Dehydration:** At end of Request, save Context (Data Zone) back to DB.

---
**Exercise:**
Write a simple FastAPI receiving `POST /add-product` and calling `add_product` process of Theus. Handle try/except to return appropriate HTTP error codes.
