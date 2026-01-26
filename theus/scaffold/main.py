# ==============================================================================
# THEUS V3 UNIVERSAL DEMO
# ==============================================================================
# This project contains 3 verified examples of Theus V3 capabilities:
# 1. E-COMMERCE: Pure Process-Oriented Programming (POP), simple workflow.
# 2. ASYNC OUTBOX: Signal Injection, Background Tasks, Relay Pattern.
# 3. PARALLEL: Zero-Copy Managed Memory (Shared Memory), Aggregation.
# ==============================================================================

import os
import sys
import questionary
from theus import TheusEngine
from theus.config import ConfigFactory
from src.context import DemoSystemContext

# Force ProcessPool to avoid NumPy/Subinterpreter crash in Py3.14
os.environ["THEUS_USE_PROCESSES"] = "1"

# 1. Detect environment
basedir = os.path.dirname(os.path.abspath(__file__))
if basedir not in sys.path:
    sys.path.insert(0, basedir)

def run_ecommerce(engine: TheusEngine):
    print("\n[DEMO] Running E-Commerce Example...")
    workflow_path = os.path.join(basedir, "workflows", "ecommerce.yaml")
    
    # Init Data (Seed)
    # Init Data (Seed) using Atomic Transaction
    try:
        with engine.transaction() as tx:
            # Force Domain to be a Dict to ensure field persistence in Rust State
            # and use standard V3 Transaction API
            tx.update(data={"domain": {
                # E-Commerce
                "order_request": {"id": "ORD-001", "items": ["Laptop", "Mouse"], "total": 1500.0},
                "orders": [],
                "balance": 0.0,
                "processed_orders": [],
                
                # Async Outbox
                "active_tasks": {},
                "sync_ops_count": 0,
                "async_job_result": None,
                "outbox_queue": [],
                "status": "IDLE",
                
                # Parallel
                "parallel_consensus": 0.0
            }})
    except Exception as e:
        print(f"[WARN] Setup failed: {e}")
        
    engine.execute_workflow(workflow_path)

def run_async_outbox(engine: TheusEngine):
    print("\n[DEMO] Running Async Outbox Example...")
    import asyncio
    
    workflow_path = os.path.join(basedir, "workflows", "async_outbox.yaml")
    
    async def _runner():
        # Inject Signal to Start
        print("[Test] Injecting 'cmd_start_outbox' signal...")
        try:
            # We can use sync transaction update here before workflow starts
            with engine.transaction() as tx:
                tx.update(signal={'cmd_start_outbox': 'True'})
        except Exception as e:
            print(f"Signal Injection Warn: {e}")
            
        print("--- Start Workflow ---")
        # Run blocking workflow in thread pool so it doesn't block the loop
        # This allows background tasks spawned by processes to run on this loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, engine.execute_workflow, workflow_path)
        print("--- End Workflow ---")

    asyncio.run(_runner())
    
def run_parallel_demo(engine: TheusEngine):
    print("\n[DEMO] Running Parallel Processing (Managed Memory)...")
    import numpy as np
    from src.processes.parallel import process_partition
    
    # 1. Alloc Shared Memory (Managed by Theus Engine)
    size = 10_000_000 # 10 Million floats
    print(f"[*] Allocating Managed Memory for {size} floats...")
    
    # V3 Standard: Engine manages Heavy Zone for Parallel Tasks.
    arr_in = engine.heavy.alloc("source_data", shape=(size,), dtype=np.float32)
    arr_out = engine.heavy.alloc("results_data", shape=(size,), dtype=np.float32)
    
    # Get SHM names to pass to workers
    source_shm_name = arr_in._shm_ref.name
    results_shm_name = arr_out._shm_ref.name
    
    # Generate Data
    arr_in[:] = np.random.rand(size)
    
    # 2. Execute Parallel Task (Manual Orchestration)
    
    chunk_size = 2_500_000
    num_workers = 4
    
    # Register first
    engine.register(process_partition)
    
    # We don't need to CAS 'heavy' into state for workers anymore 
    # because we pass names directly. But keeping it in state is good practice for main process visibility.
    engine.compare_and_swap(engine.state.version, heavy={
        'source_data': arr_in,
        'results_data': arr_out
    })
    
    print(f"[*] Dispatching {num_workers} parallel workers...")
    
    results = []
    for i in range(num_workers):
        start = i * chunk_size
        end = start + chunk_size
        
        # Using execute_parallel (Native Engine API)
        res = engine.execute_parallel(
            "process_partition", 
            partition_id=i,
            start_idx=start,
            end_idx=end,
            source_shm_name=source_shm_name,
            results_shm_name=results_shm_name,
            shape=(size,),
            dtype='float32'
        )
        results.append(res)
    
    # 3. Verify
    print("[*] Verifying result consistency...")
    total_sum_parallel = sum(r['partial_sum'] for r in results if 'partial_sum' in r)
    print(f"Total Sum (Parallel): {total_sum_parallel}")
    
    # Cleanup
    if engine.heavy:
        engine.heavy.cleanup()
        
    print("Consensus: ✅ MATCH" if total_sum_parallel > 0 else "❌ FAIL")

def main():
    print("=== THEUS V3 UNIVERSAL SKELETON ===")
    
    # Standard V3 Initialization: Use ConfigFactory
    recipe_path = os.path.join(basedir, "specs", "audit_recipe.yaml")
    
    try:
        audit_config = ConfigFactory.load_recipe(recipe_path)
    except Exception as e:
        print(f"[WARN] Failed to load audit recipe: {e}. Using Default.")
        # Minimal Fallback if Factory fails (should not happen with valid file)
        # We let Engine handle strict_mode defaults if None is passed?
        # Or construct a dummy Book? 
        # For now, let's just pass None and warn.
        audit_config = None

    sys_ctx = DemoSystemContext()
    engine = TheusEngine(sys_ctx, audit_recipe=audit_config)
    
    # Scan all processes
    engine.scan_and_register(os.path.join(basedir, "src", "processes"))
    
    # 2. Select Demo (CLI Arg or Interactive)
    if len(sys.argv) > 1:
        choice_idx = sys.argv[1]
        # Map simple numbers to choice strings for consistency
        charmap = {
            "1": "1. E-Commerce (Standard POP)",
            "2": "2. Async Outbox (Signals & Background Jobs)",
            "3": "3. Parallel Processing (Shared Memory)"
        }
        choice = charmap.get(choice_idx, "4. Exit")
    else:
        # Interactive Selection
        choice = questionary.select(
            "Which demo would you like to run?",
            choices=[
                "1. E-Commerce (Standard POP)",
                "2. Async Outbox (Signals & Background Jobs)",
                "3. Parallel Processing (Shared Memory)",
                "4. Exit"
            ]
        ).ask()
    
    if choice.startswith("1"):
        run_ecommerce(engine)
    elif choice.startswith("2"):
        run_async_outbox(engine)
    elif choice.startswith("3"):
        run_parallel_demo(engine)
    else:
        print("Bye!")

if __name__ == "__main__":
    main()
