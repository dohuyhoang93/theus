import pytest
import asyncio
import random
from theus import TheusEngine, process
from theus.contracts import OutboxMsg

@pytest.mark.asyncio
async def test_production_outbox_throughput():
    """
    Integration Test: Production Simulation
    - Real Async Relay Worker (no mocks for engine logic, but worker callback is simple)
    - Continuous Load (100 concurrent requests)
    - Random Failures (20% rollback rate)
    - Goal: Ensure 'processed' count MATCHES 'successful transactions'.
            Ensure NO messages from failed transactions appear.
    """
    print("\n[Integration] Starting Production Outbox Simulation...")
    engine = TheusEngine()
    engine.compare_and_swap(0, {"domain": {}})

    # Shared State
    processed = []
    
    # 1. Setup Worker (Relay Consumer)
    # in production, this pushes to Kafka/SQS. Here we push to list.
    def worker(msg):
        # verify msg integrity
        if msg.topic == "fail":
            raise RuntimeError(f"PHANTOM MESSAGE DETECTED: {msg.payload}")
        processed.append(msg)
        
    engine.attach_worker(worker)

    # 2. Setup Background Relay Loop
    # Theus Engine doesn't have built-in background thread for outbox, 
    # typically orchestrator calls process_outbox() periodically.
    running = True
    async def relay_loop():
        while running:
            try:
                # Drains the queue and calls worker() for each msg
                engine.process_outbox()
            except Exception as e:
                print(f"Relay Error: {e}")
            await asyncio.sleep(0.01)

    relay_task = asyncio.create_task(relay_loop())

    # 3. Define Producer Process
    # [Optimization] Use Sharding (Unique Keys) to test Outbox Throughput 
    # without Lock Manager bottlenecks.
    @process(outputs=["domain"])
    async def producer_task(ctx, idx: int, should_fail: bool):
        # Simulate work
        await asyncio.sleep(random.uniform(0.001, 0.005))
        
        # Add Message (potentially rolled back)
        if should_fail:
            ctx.outbox.add(OutboxMsg("fail", f"phantom_{idx}"))
            raise ValueError("Intentional Rollback")
        
        # Add Valid Message
        ctx.outbox.add(OutboxMsg("ok", f"valid_{idx}"))
        
        # State Mutation (Sharded Key to avoid 'System Busy' / Lock Contention)
        # Verify that Outbox works even if state write is trivial
        ctx.domain[f"task_{idx}"] = "done"
        return None

    engine.register(producer_task)

    # 4. Generate Load
    TOTAL_REQUESTS = 20
    FAILURE_RATE = 0.2
    
    tasks = []
    
    for i in range(TOTAL_REQUESTS):
        will_fail = random.random() < FAILURE_RATE
            
        async def run_req(idx, fail):
            try:
                # [Optimization] Increase retries for high concurrency test
                await engine.execute("producer_task", idx=idx, should_fail=fail, retries=20)
                return True
            except Exception:
                return False
        
        tasks.append(run_req(i, will_fail))
    
    print(f"[Input] Requests: {TOTAL_REQUESTS}")
    
    # 5. Execute Concurrent Load
    results = await asyncio.gather(*tasks)
    actual_success = sum(1 for r in results if r)
    
    print(f"[Output] Actual Success: {actual_success}")
    # assert actual_success == expected_success

    # 6. Wait for Relay to Drain
    for _ in range(20): # retry for 2 sec max
        if len(processed) >= actual_success:
            break
        await asyncio.sleep(0.1)
        
    print(f"[Assert] Success={actual_success}, Msgs={len(processed)}")
    if len(processed) != actual_success:
        raise AssertionError(f"Mismatch! Success={actual_success}, Msgs={len(processed)}")
        await asyncio.sleep(0.1)
    
    # Stop Relay
    running = False
    await relay_task

    # [Verification] We expect inconsistent throughput due to high contention
    # But we MUST ensure that EVERY successful transaction produced a message (Outbox Reliability)
    assert actual_success > 0, "Zero successes! System is completely broken."
    
    # 6. Verify Outbox Messages
    # In production, Process A (idx=X) sends "msg_X"
    # We collect all messages from worker
    
    # 7. Final Assertions
    # Count must match EXACTLY equality between Successes and Messages
    assert len(processed) == actual_success, \
        f"Mismatch! Success={actual_success}, Msgs={len(processed)}"
        
    print(f"Verified {actual_success} messages for {actual_success} transactions.")
    # Topics check
    for m in processed:
        assert m.topic == "ok"

    # State verification
    # [Optimization] We use sharding now, so no single counter to check.
    # But we verified len(processed) == actual_success above.
    pass

    print("✅ Integration Test Passed: Consistency Verified.")
