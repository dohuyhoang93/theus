from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Annotated

from theus import TheusEngine
# Import Rust Core Exceptions for mapping
from theus_core import AuditBlockError, AuditStopError, ContextError

from src.dependencies import get_engine

app = FastAPI(title="Theus Service Layer Demo", version="1.0.0")

# --- Pydantic Models for API IO ---
class OrderRequest(BaseModel):
    order_id: str
    item_id: str
    quantity: int

class OrderResponse(BaseModel):
    status: str
    message: str

# --- Endpoints ---

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
async def root():
    """Redirect to Auto-Generated Docs."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.post("/orders", response_model=OrderResponse)
async def create_order_endpoint(
    req: OrderRequest,
    engine: Annotated[TheusEngine, Depends(get_engine)]
):
    """
    Creates a new order using Theus Engine.
    Handles business logic audit and safety checks automagically.
    """
    try:
        # Await the execution (Async Engine v3)
        result = await engine.execute(
            "create_order", 
            order_id=req.order_id, 
            item_id=req.item_id, 
            qty=req.quantity
        )
        
        return OrderResponse(status="success", message=f"Order {req.order_id} processed.")
        
    except ValueError as e:
        # Business Logic Error (e.g. Insufficient Stock)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
        
    except AuditBlockError as e:
        # Policy Violation (Blocked by Rust Core)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, # Or 400/403
            detail=f"Transaction Blocked by Audit Policy: {e}"
        )
        
    except ContextError as e:
        # Concurrency/CAS Conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="State Conflict. Please retry."
        )

@app.get("/inventory/{item_id}")
async def get_inventory(
    item_id: str,
    engine: Annotated[TheusEngine, Depends(get_engine)]
):
    # Direct READ via Engine State (Zero-Copy Read)
    # No need for transaction just for reading
    inventory = engine.state.data.get("domain", {}).get("inventory", {})
    count = inventory.get(item_id, 0)
    return {"item_id": item_id, "stock": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
