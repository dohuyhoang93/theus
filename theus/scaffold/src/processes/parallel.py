
import numpy as np
import os
from theus.contracts import process
from multiprocessing.shared_memory import SharedMemory

@process(parallel=True)
def process_partition(ctx):
    """
    Processes a specific partition of the shared data.
    """
    # 1. Get Inputs (Lightweight metadata)
    p_id = ctx.input.get('partition_id')
    start = ctx.input.get('start_idx')
    end = ctx.input.get('end_idx')
    
    source_shm_name = ctx.input.get('source_shm_name')
    results_shm_name = ctx.input.get('results_shm_name')
    shape = ctx.input.get('shape')
    dtype = np.dtype(ctx.input.get('dtype'))
    
    # 2. Attach to Shared Memory (Zero-Copy)
    # Note: Workers attach to existing SharedMemory by name.
    # They do NOT receive ctx.heavy (unpicklable).
    try:
        source_shm = SharedMemory(name=source_shm_name, create=False)
        results_shm = SharedMemory(name=results_shm_name, create=False)
        
        input_data = np.ndarray(shape, dtype=dtype, buffer=source_shm.buf)
        output_data = np.ndarray(shape, dtype=dtype, buffer=results_shm.buf)
        
        # 3. Process Partition (CPU Bound)
        chunk = input_data[start:end]
        processed = np.power(chunk, 2)
        output_data[start:end] = processed
        
        # 4. Return Delta (Aggregation Metadata)
        local_sum = float(np.sum(processed))
        
        # Cleanup handles
        source_shm.close()
        results_shm.close()
        
        return {
            "p_id": p_id,
            "partial_sum": local_sum,
            "rows_processed": (end - start),
            "pid": os.getpid()
        }
    except Exception as e:
         return {"error": str(e), "pid": os.getpid()}

@process(parallel=True)
def saboteur_task(ctx):
    """
    Attempts to destroy the shared memory provided to it.
    """
    source_shm_name = ctx.input.get('source_shm_name')
    if not source_shm_name:
         return {"status": "NO_SHM_NAME"}

    try:
        shm = SharedMemory(name=source_shm_name, create=False)
        # Attempt to unlink (Destroy)
        shm.unlink()
        shm.close()
        return {"status": "DESTROYED"}
    except PermissionError:
        return {"status": "BLOCKED"}
    except FileNotFoundError:
        return {"status": "NOT_FOUND"}
    except Exception as e:
        return {"status": f"ERROR: {e}"}
