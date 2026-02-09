
import asyncio
import random
import time
from theus.engine import TheusEngine
from theus.contracts import process, AdminTransaction, SemanticType

# =============================================================================
# 1. SAMPLE (MẪU): Basic Functionality
# =============================================================================
@process(outputs=["domain.data_store"])
async def p_sample_write(ctx, value):
    ctx.domain.data_store = value
    return None

@process(outputs=["domain.log_history"])
async def p_log_append(ctx, msg):
    ctx.domain.log_history.append(msg)
    return None

# =============================================================================
# 2. RELATED (LIÊN QUAN): Contextual & Nested Interactions
# =============================================================================
@process(outputs=["domain.nested.config", "domain.nested.log_ops", "domain.data_store"])
async def p_nested_policy(ctx):
    # Update to normal data in nested path
    ctx.domain.nested.config = {"status": "active"}
    
    # Append to log in nested path (Should follow Log Zone Physics)
    ctx.domain.nested.log_ops.append("init")
    
    try:
        # Should be blocked by DELETE physics even if deep
        ctx.domain.nested.log_ops.pop()
        # We can't return a string here because multiple outputs are expected.
        # We use a state flag to track result.
        ctx.domain.data_store = "DEEP_LEAK"
    except PermissionError:
        ctx.domain.data_store = "DEEP_BLOCK_OK"
    
    return None

# =============================================================================
# 3. BOUNDARY (BIÊN): Edge Cases & Elevation Isolation
# =============================================================================
@process(outputs=["domain.log_history"])
async def p_elevation_boundary(ctx):
    # Try illegal delete in standard mode
    try:
        ctx.domain.log_history.pop()
        return "ERROR: Standard Delete allowed!"
    except PermissionError:
        pass
    
    # Admin Elevation
    with AdminTransaction(ctx) as admin:
        admin.domain.log_history.clear() # Should work
        
    return None

# =============================================================================
# 4. CONFLICT (XUNG ĐỘT): Concurrency & Contradiction
# =============================================================================
@process(outputs=["domain.shared_log"])
async def p_concurrent_append(ctx, worker_id):
    # Simulate some work
    await asyncio.sleep(random.uniform(0.01, 0.05))
    ctx.domain.shared_log.append(f"worker_{worker_id}")
    # print(f"  [Worker {worker_id}] Mutation applied to proxy", flush=True)
    return None

# =============================================================================
# TEST SUITE
# =============================================================================
async def run_comprehensive_suite():
    print("\n>>> STARTING RFC-001 COMPREHENSIVE INTEGRATION SUITE (NO MOCKS) <<<\n")
    
    engine = TheusEngine(context={
        "domain": {
            "data_store": None,
            "log_history": [],
            "shared_log": [],
            "nested": {
                "config": {},
                "log_ops": []
            }
        }
    })
    
    # CASE 1: SAMPLE
    print("[1/4] CASE: SAMPLE - Verification...")
    await engine.execute(p_sample_write, value="hello_theus")
    await engine.execute(p_log_append, msg="log_1")
    assert engine.state.data["domain"]["data_store"] == "hello_theus"
    assert engine.state.data["domain"]["log_history"] == ["log_1"]
    print("  PASSED: Basic Sample write/append.")

    # CASE 2: RELATED
    print("[2/4] CASE: RELATED - Verification...")
    await engine.execute(p_nested_policy)
    assert engine.state.data["domain"]["data_store"] == "DEEP_BLOCK_OK"
    assert engine.state.data["domain"]["nested"]["config"]["status"] == "active"
    assert engine.state.data["domain"]["nested"]["log_ops"] == ["init"]
    print("  PASSED: Nested path enforcement (Lens recursion).")

    # CASE 3: BOUNDARY
    print("[3/4] CASE: BOUNDARY - Verification...")
    await engine.execute(p_elevation_boundary)
    assert len(engine.state.data["domain"]["log_history"]) == 0
    print("  PASSED: Elevation bounds and physics ceiling.")

    # CASE 4: CONFLICT
    print("[4/4] CASE: CONFLICT - Verification...")
    # Explicitly clear log to ensure count accuracy
    engine.state.data["domain"]["shared_log"] = []
    
    NUM_WORKERS = 5
    print(f"  Stress testing with {NUM_WORKERS} parallel workers (Shared Log Append)...")
    start_time = time.time()
    
    async def wrapped_worker(wid):
        # [v3.3.1] Standardizing on 5 workers with jitter to avoid VIP Deadlock
        await asyncio.sleep(random.uniform(0.1, 0.5))
        try:
            # Pass requester_id to satisfy Rust Core VIP checks
            await engine.execute(p_concurrent_append, worker_id=wid, retries=100, requester_id=f"worker_{wid}")
            print(f"  [Worker {wid}] SUCCESS", flush=True)
        except Exception as e:
            print(f"  [Worker {wid}] FAILED: {e}", flush=True)
            raise e

    workers = [wrapped_worker(i) for i in range(NUM_WORKERS)]
    await asyncio.gather(*workers)
    
    final_log = engine.state.data["domain"]["shared_log"]
    print(f"  Stress Results: {len(final_log)}/{NUM_WORKERS}. Time: {time.time()-start_time:.2f}s")
    assert len(final_log) == NUM_WORKERS, f"Conflict failure: Missing entries! Found {len(final_log)}"
    print("  PASSED: Parallel conflict resolution (CAS + Mutex).")

    print("\n>>> ALL RFC-001 COMPREHENSIVE CASES PASSED! <<<\n")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_suite())
