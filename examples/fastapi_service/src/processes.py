import random
from theus.contracts import process

# --- Business Logic ---

@process(inputs=["domain.inventory"], outputs=["domain.orders", "domain.inventory*"])
def create_order(ctx, order_id: str, item_id: str, qty: int):
    """
    Process an order request.
    Validates inventory and updates state.
    """
    # 1. Read State
    inventory = ctx.domain.inventory
    current_stock = inventory.get(item_id, 0)
    
    # 2. Logic / Validation
    if current_stock < qty:
        raise ValueError(f"Insufficient stock for {item_id}. Requested: {qty}, Available: {current_stock}")
    
    # 3. Compute Changes
    new_stock = current_stock - qty
    
    order_record = {
        "id": order_id,
        "item_id": item_id,
        "qty": qty,
        "status": "confirmed"
    }
    
    # 4. Return Updates (Declarative)
    # Use StateUpdate for granular deep-patching
    from theus.structures import StateUpdate
    return StateUpdate(data={
        f"domain.inventory.{item_id}": new_stock,
        f"domain.orders.{order_id}": order_record
    })

@process(inputs=[], outputs=["domain.orders"])
def cancel_order(ctx, order_id: str):
    """
    Cancels an order.
    Demonstrates simple state update.
    """
    if order_id not in ctx.domain.orders:
        raise KeyError(f"Order {order_id} not found")
        
    return {
        f"domain.orders.{order_id}.status": "cancelled"
    }
