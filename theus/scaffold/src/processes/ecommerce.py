from theus.contracts import process
from theus.contracts import SemanticType
from src.context import DemoSystemContext


@process(inputs=["ecommerce.order_request"], outputs=["ecommerce.log_orders"])
def create_order(ctx: DemoSystemContext):
    """
    Creates an order from request.
    Audit Rule: Blocks if price <= 0.
    POP: Returns updated order list.
    """
    req = ctx.ecommerce.order_request

    if not hasattr(req, "get"):
        raise ValueError("Invalid request format")

    # Logic: Appends to order list
    current_orders = ctx.ecommerce.log_orders
    total = req.get("total", 0)
    if total <= 0:
        raise ValueError(f"Invalid total: {total}")

    new_order = {"id": req.get("id"), "items": req.get("items", []), "total": total}

    # RFC-001: Append-Only logic (return full list for the Delta)
    updated = list(current_orders) + [new_order]

    ctx.log.info(f"[Ecommerce] Order created: {new_order['id']}")
    return updated


@process(
    inputs=["ecommerce.log_orders"], 
    outputs=["ecommerce.balance", "ecommerce.log_processed"]
)
def process_payment(ctx: DemoSystemContext):
    """
    Processes payment for pending orders.
    POP: Returns (balance, processed_list).
    """
    orders = ctx.ecommerce.log_orders
    balance = ctx.ecommerce.balance
    processed = ctx.ecommerce.log_processed

    for order in orders:
        if order["id"] in processed:
            continue

        amount = order["total"]
        balance += amount  # Revenue
        processed.append(order["id"])

    ctx.log.info(f"[Ecommerce] Payment processed. New Balance: {balance}")
    ctx.log.info("[Ecommerce] Invoice image stored in HEAVY zone")
    return balance, processed


@process(
    inputs=["ecommerce.log_orders"],
    outputs=["heavy.invoice_img"],
    semantic=SemanticType.EFFECT,
)
def store_invoice_image(ctx: DemoSystemContext):
    """
    Demonstrates HEAVY zone usage (Zero-Copy).
    POP: Returns bytearray for heavy output.
    """
    import random

    # Simulate generating a large image (byte array)
    large_data = bytearray(random.getrandbits(8) for _ in range(1024 * 1024))

    ctx.log.info("[Ecommerce] Invoice image stored in HEAVY zone")
    return large_data
