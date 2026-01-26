
import time
import math
import threading
import os
import sys
import asyncio
from theus.engine import TheusEngine
from theus.contracts import ProcessContract as Contract, SemanticType

# 1. Define a CPU-heavy task
def cpu_heavy_task(n):
    """
    Naive prime check for CPU load.
    Returns metadata to identify execution context.
    """
    count = 0
    start = time.time()
    for i in range(2, n):
        is_prime = True
        for j in range(2, int(math.sqrt(i)) + 1):
            if i % j == 0:
                is_prime = False
                break
        if is_prime:
            count += 1
    
    duration = time.time() - start
    return {
        "primes": count,
        "duration": duration,
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "thread_name": threading.current_thread().name
    }

# 2. Register process with Theus
def run_heavy_load(ctx):
    # Simulate a heavy load ~500ms-1s depending on CPU
    return cpu_heavy_task(100000)

run_heavy_load._pop_contract = Contract(
    inputs=["domain"],
    outputs=["domain"],
    semantic=SemanticType.PURE  # or PROCESS
)

async def main():
    print(f"Main Process ID: {os.getpid()}")
    print(f"Main Thread ID: {threading.get_ident()}")
    
    engine = TheusEngine()
    engine.register(run_heavy_load)
    
    # 3. Test 1: Run Serial (Baseline)
    print("\n--- Running Serial Baseline (2 tasks) ---")
    start_serial = time.time()
    try:
        res1 = await engine.execute("run_heavy_load")
    except Exception as e:
        print(f"Serial Task 1 failed: {e}")
        res1 = {}
    
    try:
        res2 = await engine.execute("run_heavy_load")
    except Exception as e:
        print(f"Serial Task 2 failed: {e}")
        res2 = {}
    end_serial = time.time()
    serial_time = end_serial - start_serial
    print(f"Serial Time: {serial_time:.4f}s")
    print(f"Task 1 Context: PID={res1['pid']}, TID={res1['tid']} ({res1['thread_name']})")
    print(f"Task 2 Context: PID={res2['pid']}, TID={res2['tid']} ({res2['thread_name']})")

    # 4. Test 2: Run Parallel (Concurrent)
    print("\n--- Running Parallel/Concurrent (2 tasks) ---")
    start_parallel = time.time()
    # Launch both at once
    task1 = asyncio.create_task(engine.execute("run_heavy_load"))
    task2 = asyncio.create_task(engine.execute("run_heavy_load"))
    
    try:
        res_p1 = await task1
    except Exception as e:
        print(f"Parallel Task 1 failed (expected CAS error): {e}")
        # We need the task result to inspect TID, but if it failed in engine, we might not get the return value.
        # But cpu_heavy_task runs BEFORE commit. The error happens at commit.
        # Theus engine does NOT return result if commit fails? 
        # In engine.py: result = await self._core.execute_process_async... then commit.
        # If commit fails, it raises. We lose the result.
        # I need to modify checking logic.
        res_p1 = {"pid": "N/A", "tid": "N/A", "thread_name": "Error"}

    try:
        res_p2 = await task2
    except Exception as e:
        print(f"Parallel Task 2 failed (expected CAS error): {e}")
        res_p2 = {"pid": "N/A", "tid": "N/A", "thread_name": "Error"}
    end_parallel = time.time()
    parallel_time = end_parallel - start_parallel
    
    print(f"Parallel Time: {parallel_time:.4f}s")
    print(f"Task 1 Context: PID={res_p1['pid']}, TID={res_p1['tid']} ({res_p1['thread_name']})")
    print(f"Task 2 Context: PID={res_p2['pid']}, TID={res_p2['tid']} ({res_p2['thread_name']})")
    
    # 5. Analysis
    print("\n--- ANALYSIS ---")
    speedup = serial_time / parallel_time
    print(f"Speedup: {speedup:.2f}x")
    
    if speedup < 1.5:
        print("❌ RESULT: NO PARALLELISM DETECTED (GIL Bound)")
        print("   Explanation: Speedup is close to 1.0x, meaning tasks ran sequentially due to GIL.")
        if res_p1['tid'] != res_p2['tid']:
             print("   Note: Tasks ran on DIFFERENT threads, confirming standard Threading + GIL.")
    else:
        print("✅ RESULT: TRUE PARALLELISM DETECTED")
        print("   Explanation: Speedup is close to 2.0x, meaning tasks bypassed GIL.")

if __name__ == "__main__":
    asyncio.run(main())
