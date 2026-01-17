
# Standalone module for testing True Parallelism
# MUST NOT import anything from 'theus' to ensure sub-interpreter isolation safety.

def pure_cpu_bound_task(x, y):
    """
    A pure python function that uses CPU.
    """
    import os
    import threading
    import math
    
    # Simulate heavy work
    res = 0
    for i in range(1000):
        res += math.sqrt(x * x + y * y + i)
        
    return {
        "result": res,
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "context": "isolated_module"
    }
