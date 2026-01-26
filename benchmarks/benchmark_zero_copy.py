
import time
import numpy as np
import multiprocessing
import multiprocessing.pool
import multiprocessing.shared_memory
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# Constants
MATRIX_SIZE = 3000 # 3000x3000 float64 ~ 72MB
NUM_WORKERS = 4

def output(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# --- Tasks ---

def task_sequential_compute(arr):
    """Heavy Compute: Matrix Power"""
    return np.dot(arr, arr)

def task_io_bound(_):
    """IO Bound: Sleep"""
    time.sleep(0.5)
    return "done"

# --- Models ---

def run_sequential(arr):
    start = time.time()
    for _ in range(NUM_WORKERS):
        task_sequential_compute(arr)
    return time.time() - start

def run_threaded(arr):
    start = time.time()
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as exe:
        futures = [exe.submit(task_sequential_compute, arr) for _ in range(NUM_WORKERS)]
        [f.result() for f in futures]
    return time.time() - start

def _mp_worker(arr):
    return np.dot(arr, arr)

def run_multiprocessing_pickle(arr):
    """Standard MP (Deep Copy input)"""
    start = time.time()
    with multiprocessing.get_context("spawn").Pool(NUM_WORKERS) as p:
        # Note: 'arr' is pickled and sent to each worker
        results = [p.apply_async(_mp_worker, (arr,)) for _ in range(NUM_WORKERS)]
        [r.get() for r in results]
    return time.time() - start

# --- Zero Copy (Smart Pickle) ---

def _smart_worker(arr):
    # arr here is a ShmArray (reconstructed automatically via pickle)
    # This proves the "Engine Wiring" prevents the copy.
    res = np.dot(arr, arr)
    return res.shape

def run_smart_zerocopy(arr):
    """Uses Theus ShmArray to implicitly achieve Zero-Copy via Smart Pickling"""
    start = time.time()
    
    # 1. Promote to ShmArray (Theus "Heavy Zone" Logic)
    # Allocate Shared Memory
    shm = multiprocessing.shared_memory.SharedMemory(create=True, size=arr.nbytes)
    # Copy Data Once (Producer side)
    shared_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
    shared_arr[:] = arr[:]
    
    # Wrap in Theus Object
    from theus.context import ShmArray
    # Note: We must ensure 'shm' handle stays open while workers are using it?
    # Python pickle transfer: The worker opens its OWN handle via name.
    # The Main process must keep ITS handle open (or at least the file backing it must exist).
    # ShmArray holds 'shm'.
    theus_obj = ShmArray(shared_arr, shm=shm)
    
    prep_time = time.time() - start
    
    # 2. Workers (receive OBJECT, but Pickle magic sends REFERENCE)
    with multiprocessing.get_context("spawn").Pool(NUM_WORKERS) as p:
        results = [
            p.apply_async(_smart_worker, (theus_obj,)) 
            for _ in range(NUM_WORKERS)
        ]
        [r.get() for r in results]
        
    total_time = time.time() - start
    
    # Cleanup
    shm.close()
    shm.unlink()
    
    return total_time, prep_time

# --- Full API Benchmark (TheusEngine) ---

from zc_tasks import process_heavy_task, process_simple_task

def run_theus_engine(arr):
    """Uses TheusEngine + @process API"""
    from theus.engine import TheusEngine
    from theus.context import ShmArray
    
    start = time.time()
    
    # FORCE PROCESS BACKEND (NumPy compat)
    os.environ["THEUS_USE_PROCESSES"] = "1"
    
    # 1. Allocate SHM (Producer)
    shm = multiprocessing.shared_memory.SharedMemory(create=True, size=arr.nbytes)
    shared_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
    shared_arr[:] = arr[:]
    theus_obj = ShmArray(shared_arr, shm=shm)
    
    prep_time = time.time() - start
    
    # 2. Initialize Engine with Mock State
    # Note: We need a context that has 'heavy'
    # 2. Initialize Engine with Real State
    from dataclasses import dataclass, field
    from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

    @dataclass
    class BenchDomain(BaseDomainContext):
        pass

    @dataclass
    class BenchGlobal(BaseGlobalContext):
        pass

    @dataclass
    class BenchContext(BaseSystemContext):
        domain: BenchDomain
        global_ctx: BenchGlobal

    
    # helper to force dictionary hydration including 'heavy'
    ctx = BenchContext(domain=BenchDomain(), global_ctx=BenchGlobal())
    init_data = ctx.to_dict()
    init_data['heavy'] = {} # FORCE ROOT KEY

    # Init Engine with None, then Manual CAS
    engine = TheusEngine(context=None, strict_mode=False)
    engine.compare_and_swap(0, init_data)

    
    # Inject Heavy Data using CAS (Correct Way)
    # TheusEngine checks if core state is available
    res = engine.compare_and_swap(engine.state.version, heavy={'matrix': theus_obj})
    print(f"DEBUG: CAS Result: {res}")
    
    # Verify Injection locally (Retry loop for convergence)
    
    for _ in range(10):
        try:
             # Workaround: FrozenDict __contains__ might be buggy or strict
             if 'matrix' in list(engine.state.heavy.keys()):
                 break
        except Exception:
             pass
        time.sleep(0.1)
        
    if 'matrix' not in list(engine.state.heavy.keys()):
        # Debug: Print available keys
        print(f"DEBUG: Available Heavy Keys: {list(engine.state.heavy.keys())}")
        raise RuntimeError("CAS Failed to inject 'matrix' into Heavy Zone")

    print(f"DEBUG: Heavy Keys: {list(engine.state.heavy.keys())}")
    
    # 3. Register Process
    engine.register(process_heavy_task)
    
    # 4. Execute Parallel
    
    # Define Args
    task_args = {
        "shm_name": shm.name,
        "shape": arr.shape,
        "dtype": str(arr.dtype)
    }
    
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as exe:
        # Pass kwargs to execute_parallel
        futures = [exe.submit(engine.execute_parallel, "process_heavy_task", **task_args) for _ in range(NUM_WORKERS)]
        [f.result() for f in futures]
        
    total_time = time.time() - start
    
    # Cleanup
    shm.close()
    shm.unlink()
    
    return total_time, prep_time

# --- Main ---

if __name__ == "__main__":
    # Ensure project root is in path for imports
    import sys
    import os
    sys.path.append(os.getcwd())

    print("=== Comprehensive Benchmark (Smart Wiring) ===")
    print(f"Matrix: {MATRIX_SIZE}x{MATRIX_SIZE} | Workers: {NUM_WORKERS}")
    
    # Create Heavy Data
    data = np.random.rand(MATRIX_SIZE, MATRIX_SIZE)
    print(f"Data Size: {data.nbytes / 1024 / 1024:.2f} MB")
    print("-" * 30)

    # 1. Sequential
    t_seq = run_sequential(data)
    print(f"1. Sequential:      {t_seq:.4f}s (Baseline)")

    # 2. Threaded
    t_thread = run_threaded(data)
    print(f"2. Threaded (GIL):  {t_thread:.4f}s (Speedup: {t_seq/t_thread:.2f}x)")

    # 3. MP (Pickle)
    t_mp = run_multiprocessing_pickle(data)
    print(f"3. MP (Pickle):     {t_mp:.4f}s (Speedup: {t_seq/t_mp:.2f}x)")

    # 4. Zero Copy (Smart)
    t_zc, t_prep = run_smart_zerocopy(data)
    print(f"4. Theus Smart-ZC:  {t_zc:.4f}s (Speedup: {t_seq/t_zc:.2f}x)")
    print(f"   (Prep/Copy Time: {t_prep:.4f}s included)")
    
    print("-" * 30)
    if t_zc < t_mp:
        print(f"✅ SUCCESS: Smart-Pickle is {t_mp/t_zc:.2f}x faster than Pickle MP!")
    else:
        print("⚠️ RESULT: Smart-Pickle did not optimize. Check __reduce__ logic.")

    # 5. Full API
    try:
        t_api, t_prep_api = run_theus_engine(data)
        print(f"5. Theus API:       {t_api:.4f}s (Speedup: {t_seq/t_api:.2f}x)")
        print(f"   (Overhead vs Core: {t_api - t_zc:.4f}s)")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"5. Theus API:       FAILED ({e})")
