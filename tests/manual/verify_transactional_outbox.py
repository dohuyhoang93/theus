import asyncio
import time
from theus import TheusEngine, process

# Goal: Verify Chapter 18 - Transactional Outbox Pattern
# Pattern:
# 1. Producer: Adds message to 'domain.outbox' inside a Transaction (StateUpdate).
# 2. Relay: Reads 'domain.outbox', Sends, then Clears 'domain.outbox' via CAS.

# --- Domain Producer ---
@process(inputs=["domain.outbox"], outputs=["domain.outbox"])
def create_order_event(ctx):
    # Retrieve current queue or init
    current_queue = ctx.domain.get("outbox", [])
    
    # Create Message
    msg = {"id": f"msg_{int(time.time()*1000)}", "event": "ORDER_CREATED"}
    
    # Append (Immutable style)
    new_queue = list(current_queue)
    new_queue.append(msg)
    
    # Return Update
    return {"domain.outbox": new_queue}

# --- Verification Script ---
async def run_outbox_verification():
    print("==============================================")
    print("   THEUS OUTBOX PATTERN VERIFICATION (CHAP 18) ")
    print("==============================================")
    
    engine = TheusEngine()
    
    # Init State
    engine.compare_and_swap(0, {"domain": {"outbox": []}})
    engine.register(create_order_event)

    print("\n[Step 1] Producer: Creating 3 Events...")
    for _ in range(3):
        await engine.execute("create_order_event")
        
    # Verify State has 3 messages
    state = engine.state
    outbox = state.domain.get("outbox", [])
    print(f"   State Outbox Count: {len(outbox)}")
    if len(outbox) == 3:
        print("   ✅ Events persisted in State.")
    else:
        print(f"   ❌ FAILURE: Expected 3 events, found {len(outbox)}")
        return

    print("\n[Step 2] System Relay (Consumer): Processing...")
    
    # Relay Logic (Simplified)
    # 1. Read
    current_ver = state.version
    messages_to_send = state.domain.get("outbox", [])
    
    if not messages_to_send:
        print("   ⚠️  No messages to process.")
        return

    # 2. Process (Side Effect)
    print(f"   📤 Sending {len(messages_to_send)} messages to external system...")
    sent_ids = [m["id"] for m in messages_to_send]
    print(f"   Sent IDs: {sent_ids}")

    # 3. Commit (Clear Queue)
    print("   🔒 Committing (Clearing Queue) via CAS...")
    try:
        # We update ONLY the outbox key to empty list
        # Note: In Smart CAS, we only need to touch the keys we change.
        engine.compare_and_swap(current_ver, {"domain": {"outbox": []}})
        print("   ✅ Commit Successful.")
    except Exception as e:
        print(f"   ❌ Commit Failed: {e}")
        return

    # Final Verification
    final_state = engine.state
    final_outbox = final_state.domain.get("outbox", [])
    
    if len(final_outbox) == 0:
        print("\n   ✅ Outbox is EMPTY (Items Processed & Removed).")
        print("   🎉 TRANSACTIONAL OUTBOX VERIFIED")
    else:
        print(f"\n   ❌ Outbox NOT cleared. Count: {len(final_outbox)}")

if __name__ == "__main__":
    asyncio.run(run_outbox_verification())
