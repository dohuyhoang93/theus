import time
import os
import threading
import sys
import asyncio

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from theus import TheusEngine, process
from theus.parallel import INTERPRETERS_SUPPORTED

# Import tasks
from tests.manual.parallel_lib import task_serial, task_parallel

async def run_test_suite(engine, label):
    # Trigger lazy init by running a parallel task once
    # Use a small n to make it fast
    await engine.execute("task_parallel", n=1000) 
    backend = "Unknown"
    if hasattr(engine, "_parallel_pool") and engine._parallel_pool:
        backend = engine._parallel_pool.__class__.__name__

    print(f"\n--- Running Suite: {label} [{backend}] ---")
    
    # Baseline
    print("   [Baseline] Running 2 Serial Tasks (Threaded/GIL)...")
    start = time.time()
    await asyncio.gather(engine.execute("task_serial"), engine.execute("task_serial"))
    dur_serial = time.time() - start
    print(f"      Duration: {dur_serial:.3f}s")
    
    # Parallel
    print("   [Experiment] Running 2 Parallel Tasks...")
    start = time.time()
    await asyncio.gather(engine.execute("task_parallel"), engine.execute("task_parallel"))
    dur_parallel = time.time() - start
    print(f"      Duration: {dur_parallel:.3f}s")
    
    speedup = dur_serial / dur_parallel
    print(f"   ℹ️  Speedup: {speedup:.2f}x")
    return speedup

async def run_parallel_verification():
    print("==============================================")
    print("   THEUS PARALLELISM VERIFICATION (CHAP 19) ")
    print("==============================================")
    print(f"   Python Version: {sys.version.split()[0]}")
    
    # 1. Test Sub-interpreters (Forced for CI)
    if INTERPRETERS_SUPPORTED:
        print("\n=== MODE 1: Sub-interpreters (Experimental) ===")
        os.environ["THEUS_FORCE_INTERPRETERS"] = "1"
        os.environ.pop("THEUS_USE_PROCESSES", None)
        
        engine_sub = TheusEngine()
        engine_sub.register(task_serial)
        engine_sub.register(task_parallel)
        
        speedup = await run_test_suite(engine_sub, "Sub-interpreters")
        if speedup > 1.1:
            print("   ✅ Sub-interpreters working!")
        else:
            print("   ⚠️  Sub-interpreters overhead high or GIL not freed.")
            
    # 2. Test ProcessPool (Proven Fallback)
    print("\n=== MODE 2: ProcessPool (Production Standard) ===")
    os.environ["THEUS_USE_PROCESSES"] = "1"
    os.environ.pop("THEUS_FORCE_INTERPRETERS", None)
    
    # Re-init engine to pick up env var
    engine_proc = TheusEngine()
    engine_proc.register(task_serial)
    engine_proc.register(task_parallel)
    
    speedup = await run_test_suite(engine_proc, "ProcessPool")
    
    if speedup > 1.4:
        print("   ✅ ProcessPool working perfectly (>1.4x)")
    else:
        print("   ❌ ProcessPool failed to parallelize?")

    print("\n==============================================")

if __name__ == "__main__":
    asyncio.run(run_parallel_verification())
