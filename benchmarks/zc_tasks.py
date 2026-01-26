
import time
import numpy as np
from theus.contracts import process

@process(
    inputs=['domain.shm_name', 'domain.shape', 'domain.dtype'], 
    outputs=[],
    parallel=True
)
def process_heavy_task(ctx):
    """
    Heavy task for Zero-Copy Benchmark.
    Re-attaches to Shared Memory by name.
    """
    try:
        from multiprocessing.shared_memory import SharedMemory
        import numpy as np
        
        # 1. Unpack Args (Domain)
        shm_name = ctx.domain.get('shm_name')
        shape = ctx.domain.get('shape')
        dtype_str = ctx.domain.get('dtype')
        
        if not shm_name:
            raise ValueError("Missing 'shm_name' in context")
            
        # 2. Attach to Shared Memory
        shm = SharedMemory(name=shm_name, create=False)
        
        # 3. Reconstruct Array (Zero-Copy View)
        arr = np.ndarray(shape, dtype=dtype_str, buffer=shm.buf)
        
        # 4. Compute
        start = time.time()
        res = np.dot(arr, arr)
        duration = time.time() - start
        
        # Cleanup handle (important for Windows)
        shm.close()
        
        return duration
        
    except Exception as e:
        import sys
        print(f"Worker Error: {e}", file=sys.stderr)
        return -1.0

@process(inputs=[], outputs=[])
def process_simple_task(ctx):
    return "ok"
