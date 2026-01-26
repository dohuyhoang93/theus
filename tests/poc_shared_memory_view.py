
import sys
import time
import struct
import multiprocessing
from multiprocessing import shared_memory
import numpy as np

def worker(shm_name, shape, dtype_name):
    # 1. Attach to existing Shared Memory
    existing_shm = shared_memory.SharedMemory(name=shm_name)
    
    # 2. Create memoryview/numpy array from it
    # Note: This is Zero-Copy. The buffer points to the same RAM.
    c = np.ndarray(shape, dtype=dtype_name, buffer=existing_shm.buf)
    
    # 3. Verify Address
    print(f"[Worker] Array Address: {c.ctypes.data}")
    print(f"[Worker] First Element: {c[0]}")
    
    # 4. Modify (to prove write visibility)
    c[0] = 999.0
    print(f"[Worker] Modified First Element to: {c[0]}")
    
    existing_shm.close()

if __name__ == "__main__":
    print(f"Python Version: {sys.version}")
    
    # 1. Allocate Shared Memory (The Arena)
    # 100MB Float32 Array
    SHAPE = (1000, 1000) 
    DTYPE = np.float32
    size = np.prod(SHAPE) * np.dtype(DTYPE).itemsize
    
    shm = shared_memory.SharedMemory(create=True, size=int(size))
    
    # 2. Main Process View
    a = np.ndarray(SHAPE, dtype=DTYPE, buffer=shm.buf)
    a[:] = 1.0 # Initialize
    
    print(f"[Main] Array Address: {a.ctypes.data}")
    print(f"[Main] First Element Before: {a[0]}")
    
    # 3. Process Spawn (Simulating Sub-Interpreter Worker)
    p = multiprocessing.Process(target=worker, args=(shm.name, SHAPE, np.dtype(DTYPE).name))
    p.start()
    p.join()
    
    # 4. Verify Side-Effect
    print(f"[Main] First Element After: {a[0]}")
    
    # Cleanup
    shm.close()
    shm.unlink()
    
    if a[0] == 999.0:
        print("✅ SUCCESS: Zero-Copy Write Confirmed!")
    else:
        print("❌ FAILURE: Data did not sync.")
