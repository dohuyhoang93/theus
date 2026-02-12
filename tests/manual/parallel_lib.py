import time
import os
import threading
from theus import process

# CPU-bound task
def cpu_heavy(n=20000000):
    print(f"   [CPU] Heavy loop starting (n={n})...")
    start = time.time()
    count = 0
    while n > 0:
        n -= 1
        count += 1
    return time.time() - start

# 1. Serial/Threaded Task (GIL Bound)
@process(inputs=[], outputs=[], parallel=False)
def task_serial(ctx):
    dur = cpu_heavy()
    return {"dur": dur, "pid": os.getpid(), "tid": threading.get_ident()}

# 2. Parallel Task (GIL Free - Sub Interpreter)
@process(inputs=[], outputs=[], parallel=True)
def task_parallel(ctx):
    # This runs in sub-interpreter
    dur = cpu_heavy()
    return {"dur": dur, "pid": os.getpid(), "tid": threading.get_ident()}

# 3. Heavy Zone Task (Zero-Copy)
@process(inputs=["heavy.large_data"], outputs=[], parallel=True)
def analyze_large_data(ctx):
    import os
    import time
    
    start = time.time()
    
    # Access Heavy Data (Zero-Copy View)
    arr = ctx.heavy["large_data"]
    
    return {
        "pid": os.getpid(),
        "shape": arr.shape,
        "mean": float(arr.mean()),
        "access_time": time.time() - start
    }
