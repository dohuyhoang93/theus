from theus.contracts import process
from theus.contracts import SemanticType
from src.context import DemoSystemContext

@process(inputs=['domain.order_request'], outputs=['domain.orders'])
def create_order(ctx: DemoSystemContext):
    """
    Creates an order from request.
    Audit Rule: Blocks if price <= 0.
    POP: Returns updated order list.
    """
    req = ctx.domain.order_request
    # Handle SupervisorProxy (v3.1)
    if hasattr(req, "to_dict"):
        req = req.to_dict()
    
    if not hasattr(req, "get"):
         raise ValueError("Invalid request format")
    
    # Logic: Appends to order list
    current_orders = ctx.domain.orders
    total = req.get("total", 0)
    if total <= 0:
        raise ValueError(f"Invalid total: {total}")

    new_order = {
        "id": req.get("id"),
        "items": req.get("items", []),
        "total": total
    }
    
    updated = current_orders + [new_order]
    
    print(f"   [Ecommerce] Order created: {new_order['id']}")
    return updated

@process(inputs=['domain.orders'], outputs=['domain.balance', 'domain.processed_orders'])
def process_payment(ctx: DemoSystemContext):
    """
    Processes payment for pending orders.
    POP: Returns (balance, processed_list).
    """
    orders = ctx.domain.orders
    balance = ctx.domain.balance
    processed = ctx.domain.processed_orders
    
    for order in orders:
        if order['id'] in processed:
            continue
            
        amount = order['total']
        balance += amount # Revenue
        processed.append(order['id'])
        
    print(f"   [Ecommerce] Payment processed. New Balance: {balance}")
    return balance, processed

@process(inputs=['domain.orders'], outputs=['heavy.invoice_img'], semantic=SemanticType.EFFECT)
def store_invoice_image(ctx: DemoSystemContext):
    """
    Demonstrates HEAVY zone usage (Zero-Copy).
    POP: Returns bytearray for heavy output.
    """
    import random
    
    # Simulate generating a large image (byte array)
    large_data = bytearray(random.getrandbits(8) for _ in range(1024 * 1024))
    
    print("   [Ecommerce] Invoice image stored in HEAVY zone")
    return large_data
