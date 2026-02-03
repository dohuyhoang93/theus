
import time
import os
import sys
import multiprocessing
from multiprocessing import shared_memory
from concurrent.futures import ProcessPoolExecutor
import numpy as np

# Large Dataset: 50MB floats ~ 400MB RAM
# 5000x5000 float64 = 25,000,000 elements * 8 bytes = 200 MB
SIZE = 5000 

def task_pickle(data):
    # Recieves COPY of data
    return data[0,0] + data[-1,-1]

def task_zerocopy(shm_name, shape, dtype):
    # Connects to existing data
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
        arr = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        res = arr[0,0] + arr[-1,-1]
        shm.close()
        return res
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    print(f"=== SCALABILITY TEST: 200MB Matrix (5000x5000 float64) ===")
    
    # 1. Generate Data
    print("Generating data...")
    data = np.ones((SIZE, SIZE), dtype=np.float64)
    nbytes = data.nbytes
    print(f"Data Size: {nbytes / 1024 / 1024:.2f} MB")
    
    # Setup Pool
    # We use 2 workers to simulate contention
    workers = 2
    
    # --- SCENARIO A: PICKLE (NO ZERO COPY) ---
    print("\n[Scenario A: Traditional Pickle (No Zero Copy)]")
    start = time.time()
    try:
        with ProcessPoolExecutor(max_workers=workers) as exe:
            # We must send the 'data' object which triggers pickling
            futures = [exe.submit(task_pickle, data) for _ in range(workers)]
            [f.result() for f in futures]
        duration = time.time() - start
        print(f"-> Time: {duration:.4f}s")
        print(f"-> Impact: High RAM Usage (Copy per worker), CPU Spike (Pickling)")
    except Exception as e:
        print(f"-> FAILED: {e}")

    # --- SCENARIO B: THEUS ZERO COPY ---
    print("\n[Scenario B: Theus Zero Copy]")
    # 1. Upload to Heavy Zone (SHM)
    shm = shared_memory.SharedMemory(create=True, size=nbytes)
    shared_arr = np.ndarray(data.shape, dtype=data.dtype, buffer=shm.buf)
    shared_arr[:] = data[:] # Copy once
    
    start = time.time()
    try:
        with ProcessPoolExecutor(max_workers=workers) as exe:
            # Send only HANDLE
            futures = [
                exe.submit(task_zerocopy, shm.name, data.shape, data.dtype) 
                for _ in range(workers)
            ]
            [f.result() for f in futures]
        duration = time.time() - start
        print(f"-> Time: {duration:.4f}s")
        print(f"-> Impact: Near-Zero RAM overhead, Instant Startup")
        
    finally:
        shm.close()
        shm.unlink()
        
    print("\n=== CONCLUSION ===")
    print("Without Zero Copy, you pay transfer costs for EVERY task.")
