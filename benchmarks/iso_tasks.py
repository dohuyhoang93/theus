
import time
import struct
# NO numpy import to ensure Sub-interpreter compatibility
# from multiprocessing import shared_memory <-- standard lib

def process_iso_cpu(context):
    """
    Pure Python CPU Task via Zero-Copy Shared Memory.
    Input: context dict with { 'shm_name': str, 'size': int }
    Output: checksum (int)
    """
    from multiprocessing import shared_memory
    
    # context is ParallelContext object, which holds domain dict
    # Note: domain is the kwargs passed to execute_parallel
    shm_name = context.domain.get('shm_name')
    size = context.domain.get('size')
    
    if not shm_name:
        return "Error: No SHM Name"

    # 1. Attach to Shared Memory (Zero-Copy)
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
    except FileNotFoundError:
        return "Error: SHM Not Found"
        
    # 2. Zero-Copy View
    # buffer protocol access
    buf = shm.buf
    
    # 3. CPU Intensive Work (Summation)
    # Read first 1MB as ints
    # Note: memoryview slicing is zero-copy
    view = memoryview(buf)
    
    # Simple checksum: Sum first 1000 bytes
    total = 0
    limit = min(size, 10000)
    
    # Iterate raw bytes
    for i in range(limit):
        total += view[i]
        
    # MUST release view before closing shm
    view.release()
    shm.close() # Close handle (does not unlink)
    
    return total
