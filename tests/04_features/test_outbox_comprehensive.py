import pytest
import asyncio
from theus import TheusEngine, process
from theus.contracts import OutboxMsg, ContractViolationError

# ==========================================
# TEST CASE 1: SAMPLE (Happy Path)
# ==========================================
def test_outbox_sample_flow():
    """
    Case 1: Sample
    Verify basic mechanics: Add message -> Commit -> Worker receives.
    """
    engine = TheusEngine()
    received = []

    def mock_worker(msg):
        received.append(msg)

    engine.attach_worker(mock_worker)

    # 1. Commit Message
    with engine.transaction() as tx:
        tx.outbox.add(OutboxMsg("email", "hello"))
    
    # 2. Process
    engine.process_outbox()

    assert len(received) == 1
    assert received[0].topic == "email"
    assert received[0].payload == "hello"

# ==========================================
# TEST CASE 2: RELATED (Context Atomicity)
# ==========================================
def test_outbox_related_atomicity():
    """
    Case 2: Related
    Verify State Update AND Outbox Message happen atomically.
    """
    engine = TheusEngine()
    engine.compare_and_swap(0, {"domain": {"count": 0}})
    
    received = []
    engine.attach_worker(lambda m: received.append(m))

    # 1. Successful Transaction
    with engine.transaction() as tx:
        # Update State
        tx.update(data={"domain": {"count": 1}})
        # Add Message
        tx.outbox.add(OutboxMsg("event", "update_done"))
    
    engine.process_outbox()

    assert engine.state.domain["count"] == 1
    assert len(received) == 1

# ==========================================
# TEST CASE 3: BOUNDARY (Rollback Safety)
# ==========================================
def test_outbox_boundary_rollback():
    """
    Case 3: Boundary
    Verify that if a transaction fails (exception), NO message is sent.
    """
    engine = TheusEngine()
    received = []
    engine.attach_worker(lambda m: received.append(m))

    # 1. Failed Transaction
    try:
        with engine.transaction() as tx:
            tx.outbox.add(OutboxMsg("topic", "GHOST_MESSAGE"))
            raise ValueError("Boom")
    except ValueError:
        pass

    # 2. Process
    engine.process_outbox()

    # Assert EMPTY
    assert len(received) == 0
    assert engine.state.version == 0 # No state change either

# ==========================================
# TEST CASE 4: CONFLICT (Concurrent CAS)
# ==========================================
# ==========================================
# TEST CASE 4: CONFLICT (Concurrent CAS)
# ==========================================
@pytest.mark.asyncio
async def test_outbox_conflict_resolution():
    """
    Case 4: Conflict
    Verify that if CAS fails due to version mismatch, the outbox message is NOT committed.
    Uses real asyncio concurrency to force a version conflict.
    """
    engine = TheusEngine()
    # Init State
    engine.compare_and_swap(0, {"domain": {"status": "init"}})
    
    received = []
    engine.attach_worker(lambda m: received.append(m))

    # Define a slow process that will lose the race
    @process(outputs=["domain.status"])
    async def slow_producer(ctx):
        # Sleep to allow interjection
        await asyncio.sleep(0.2)
        ctx.outbox.add(OutboxMsg("topic", "victim_msg"))
        return "slow_done"

    # Define a fast process that wins
    @process(outputs=["domain.status"])
    async def fast_interrupter(ctx):
        return "fast_done"
    
    engine.register(slow_producer)
    engine.register(fast_interrupter)

    # Launch both
    # 1. Start Slow (it captures version 1)
    # 2. Start Fast immediately after
    
    # We run them as tasks
    t1 = asyncio.create_task(engine.execute("slow_producer"))
    # Small yield to let t1 start and capture version
    await asyncio.sleep(0.01) 
    
    # 2. Run Fast (bumps version to 2)
    await engine.execute("fast_interrupter")
    # v3.3 Note: slow_producer might have already retried and finished if fast_interrupter took long
    assert engine.state.version in [2, 3]
    
    # 3. Await Slow
    # It should fail CAS and retry (Theus default behavior is retry?)
    # If it retries, it eventually succeeds (version 3).
    # BUT we want to ensure the FAILED attempt (version 1->2) did not produce a message.
    # Theus engine.execute automatically retries on conflict.
    # So eventually received count should be 1.
    # IF it committed "phantom" message on failure, count would be 2?
    # Or strict CAS failure would just raise error?
    # Default is Retry.
    
    await t1
    
    # Process the queue
    engine.process_outbox()
    
    # Assertions
    # If correct: the failed attempt (v1) discarded its outbox. The retry (v2->v3) succeeded.
    # So we expect exactly 1 message.
    assert len(received) == 1
    assert received[0].payload == "victim_msg"

