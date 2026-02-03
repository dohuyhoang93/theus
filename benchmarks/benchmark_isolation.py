
import time
import os
import sys
import multiprocessing
from multiprocessing import shared_memory
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.append(os.getcwd())

from theus.engine import TheusEngine
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext
from dataclasses import dataclass

# Tasks
from benchmarks.iso_tasks import process_iso_cpu

@dataclass
class IsoSystem(BaseSystemContext):
    domain: BaseDomainContext
    global_ctx: BaseGlobalContext

def run_benchmark(use_processes: bool):
    """
    Run Benchmark with specific Isolation Mode.
    True = ProcessPool (Spawn)
    False = InterpreterPool (Sub-interpreters)
    """
    mode_name = "ProcessPool (Spawn)" if use_processes else "InterpreterPool (PEP 684)"
    os.environ["THEUS_USE_PROCESSES"] = "1" if use_processes else "0"
    os.environ["THEUS_POOL_SIZE"] = "4"
    
    print(f"\n--- Benchmarking: {mode_name} ---")
    
    # 1. Setup Shared Memory (10MB)
    data_size = 10 * 1024 * 1024 # 10 MB
    shm = shared_memory.SharedMemory(create=True, size=data_size)
    # Fill with dummy data
    shm.buf[0:100] = b'\x01' * 100
    
    try:
        # 2. Init Engine
        start_init = time.time()
        ctx = IsoSystem(domain=BaseDomainContext(), global_ctx=BaseGlobalContext())
        engine = TheusEngine(ctx)
        
        # Register Task
        engine.register(process_iso_cpu)
        
        # Pre-warm pool (Trigger lazy init)
        # Hack to measure pool startup cost specifically
        # engine.execute_parallel calls pool init internally
        init_time = time.time() - start_init
        
        # 3. Execution
        start_exec = time.time()
        
        # Submit 4 tasks
        # We pass the SHM NAME as a lightweight handle (Zero-Copy Logic)
        futures = []
        payload = {'shm_name': shm.name, 'size': data_size}
        
        # Manually invoke pool to measure submission latency + execution
        # (Bypassing some engine overhead to focus on Pool)
        # Actually, let's use engine.execute_parallel to be fair to Theus API
        
        with ThreadPoolExecutor(max_workers=4) as exe:
            futures = [
                exe.submit(engine.execute_parallel, "process_iso_cpu", **payload)
                for _ in range(4) 
            ]
            results = [f.result() for f in futures]
            
        exec_time = time.time() - start_exec
        
        print(f"Init Time (Engine+Pool): {init_time:.4f}s")
        print(f"Exec Time (4 Workers):   {exec_time:.4f}s")
        print(f"Results Checksum: {results[0]}") # Should be integer
        
        return init_time, exec_time

    finally:
        shm.close()
        shm.unlink()

if __name__ == "__main__":
    print("=== Theus Isolation Benchmark (Zero-Copy Pure Python) ===")
    
    # 1. Process Pool
    p_init, p_exec = run_benchmark(use_processes=True)
    
    # 2. Interpreter Pool
    try:
        i_init, i_exec = run_benchmark(use_processes=False)
        
        print("\n--- Comparison ---")
        print(f"Init Speedup (Interp vs Proc): {p_init / i_init:.2f}x")
        print(f"Exec Speedup (Interp vs Proc): {p_exec / i_exec:.2f}x")
        
    except Exception as e:
        print(f"\n[!] Interpreter Benchmark Failed: {e}")
        print("Note: Sub-interpreters require Python 3.13+ and 'interpreters' module.")
