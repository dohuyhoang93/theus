from theus import process
import os
import threading
import time

@process(inputs=['domain.cpu_load'], outputs=['domain.parallel_result'])
def heavy_compute(ctx):
    """
    Simulates a heavy CPU task.
    Returns details about the execution context (PID, TID) to prove parallelism.
    """
    print(f"Starting Heavy Compute... (PID={os.getpid()}, TID={threading.get_ident()})")
    
    # Simulate CPU work
    load = ctx.domain.get('cpu_load', 1000)
    result = 0
    for i in range(load * 1000):
        result += i
        
    print("Heavy Compute Finished.")
    
    return {
        "result": result,
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "is_main_thread": threading.current_thread() is threading.main_thread()
    }
