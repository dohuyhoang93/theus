from theus import process
from theus.contracts import SemanticType

@process(inputs=['domain.order_request'], outputs=['domain.orders'])
def create_order(ctx):
    """
    Creates an order from request.
    Audit Rule: Blocks if price <= 0.
    POP: Returns updated order list.
    """
    req = ctx.domain['order_request']
    
    # Handle SupervisorProxy wrapper
    if hasattr(req, 'to_dict'):
        req = req.to_dict()
        
    if not isinstance(req, dict):
         raise ValueError(f"Invalid request format: Expected dict, got {type(req)}")
    
    # Logic: Appends to order list
    current_orders = ctx.domain.get('orders', [])
    total = req.get("total", 0)
    if total <= 0:
        raise ValueError(f"Invalid total: {total}")

    new_order = {
        "id": req.get("id"),
        "items": req.get("items", []),
        "total": total
    }
    
    updated = current_orders + [new_order]
    
    print(f"Order created: {new_order['id']}")
    return updated

@process(inputs=['domain.orders'], outputs=['domain.balance', 'domain.processed_orders'])
def process_payment(ctx):
    """
    Processes payment for pending orders.
    POP: Returns (balance, processed_list).
    """
    orders = ctx.domain['orders']
    balance = ctx.domain.get('balance', 0.0)
    processed = ctx.domain.get('processed_orders', [])
    
    for order in orders:
        if order['id'] in processed:
            continue
            
        amount = order['total']
        balance += amount # Revenue
        processed.append(order['id'])
        
    return balance, processed

@process(inputs=['domain.orders'], outputs=['heavy.invoice_img'], semantic=SemanticType.EFFECT)
def store_invoice_image(ctx):
    """
    Demonstrates HEAVY zone usage (Zero-Copy).
    POP: Returns bytearray for heavy output.
    """
    import random
    
    # Simulate generating a large image (byte array)
    large_data = bytearray(random.getrandbits(8) for _ in range(1024 * 1024))
    
    print("Invoice image stored in HEAVY zone")
    return large_data

@process(inputs=[], outputs=['domain.balance'])
def trigger_rollback_test(ctx):
    """
    Intentionally raises error to test Rollback.
    Returns nothing (crashes).
    """
    raise RuntimeError("Intentional Failure for Rollback Test")
