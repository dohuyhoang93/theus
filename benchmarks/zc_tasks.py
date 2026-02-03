import time
import numpy as np
from theus import process


@process(inputs=["domain.matrix"], outputs=[], parallel=True)
def process_heavy_task(ctx):
    """
    Heavy task for Zero-Copy Benchmark (Theus v3.1 Idiomatic).
    """
    try:
        import numpy as np

        # 1. Access matrix directly from Domain (where it was injected)
        # v3.1: ctx.domain might be a dict during MP serialization
        domain = ctx.domain
        
        start = time.time()

        if isinstance(domain, dict):
             # Degraded context (Fallback)
             raw_obj = domain['matrix']
        else:
             # Full Context Object
             raw_obj = domain.matrix
            
        arr = np.asarray(raw_obj)

        # 2. Compute
        _res = np.dot(arr, arr)
        duration = time.time() - start

        return duration

    except Exception as e:
        import sys

        if isinstance(domain, dict):
             keys = list(domain.keys())
        else:
             keys = "Not a dict"
        print(f"Worker Error: {e} | Available Keys: {keys}", file=sys.stderr)
        return -1.0


@process(inputs=[], outputs=[])
def process_simple_task(ctx):
    """Tác vụ tối giản để đo overhead của Engine."""
    return "ok"
