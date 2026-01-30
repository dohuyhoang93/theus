import time
import numpy as np
from theus import process


@process(inputs=["heavy.matrix"], outputs=[], parallel=True)
def process_heavy_task(ctx):
    """
    Heavy task for Zero-Copy Benchmark (Theus v3.1 Idiomatic).
    Tự động kết nối Shared Memory thông qua Heavy Zone Auto-hydration.
    """
    try:
        import numpy as np

        # 1. Access matrix directly from Heavy Zone
        # v3.1: ctx.heavy.matrix is a ShmArray, np.asarray() makes it a zero-copy numpy view
        start = time.time()
        arr = np.asarray(ctx.heavy.matrix)

        # 2. Compute
        _res = np.dot(arr, arr)
        duration = time.time() - start

        return duration

    except Exception as e:
        import sys

        print(f"Worker Error: {e}", file=sys.stderr)
        return -1.0


@process(inputs=[], outputs=[])
def process_simple_task(ctx):
    """Tác vụ tối giản để đo overhead của Engine."""
    return "ok"
