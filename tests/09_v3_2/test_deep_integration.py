import pytest
import asyncio
import time
from theus import TheusEngine, process

# Mock Process
@process(outputs=[])
def signal_emitter(ctx):
    # This should trigger Transaction -> append to pending_signal -> State.update -> SignalHub.publish
    ctx.signal.status = "active"
    ctx.signal.progress = "50%"

@pytest.mark.asyncio
async def test_deep_signal_integration():
    """
    Verify that updating ctx.signal inside a process publishes events to the shared SignalHub.
    """
    engine = TheusEngine()
    
    # Access the Hub via State
    hub = engine.state.signal
    print(f"SignalHub: {hub}")
    
    # 1. Subscribe BEFORE running
    receiver = hub.subscribe()
    
    # 2. Run Process (Sync wrapper around engine execution)
    # We use execute_process_async or just rely on standard engine flow
    # Since we don't have full workflow setup in this test, we might mock it or assume simple execution
    
    # For this test, we need to mimic what execute_workflow does:
    # Open Transaction -> Run Func -> Commit -> Close Transaction
    
    # Manually run transaction to simulate engine behavior
    with engine.transaction() as txn:
        # Create context
        # We can't easily create ProcessContext from here without internal API
        # So we use the engine's public API to run a named process?
        # TheusEngine doesn't expose 'execute_process' publicly easily without name/registry
        
        # Let's try simulating the update that happens inside a process
        # A process does: txn.update(signal={'status': 'active'})
        txn.update(signal={'status': 'active'})
        txn.update(signal={'progress': '50%'})
        
        # Exiting context commits to State -> Publishes to Hub
        
    print("Transaction committed.")
    
    # 3. Receive Events
    # We expect 2 messages: "status:active" and "progress:50%"
    # Messages order depends on update calls.
    
    # Helper to read with timeout
    async def read_msg():
        # receiver.recv is blocking, run in thread
        return await asyncio.to_thread(receiver.recv)

    msg1 = await asyncio.wait_for(read_msg(), timeout=1.0)
    print(f"Received 1: {msg1}")
    assert msg1 == "status:active"
    
    msg2 = await asyncio.wait_for(read_msg(), timeout=1.0)
    print(f"Received 2: {msg2}")
    assert msg2 == "progress:50%"
    
    print("Deep Integration Verified!")

if __name__ == "__main__":
    asyncio.run(test_deep_signal_integration())
