from typing import Any, Dict, Optional, Union
from dataclasses import dataclass

# Re-export from Rust Core
try:
    from theus_core import State, FrozenDict, ContextError
except ImportError:
    # Fallback for type checking / IDE / pre-compilation
    class ContextError(Exception): pass
    class State:
        def __init__(self, data=None, heavy=None): pass
        def update(self, data=None, heavy=None): pass
        @property
        def data(self): pass
        @property
        def heavy(self): pass
    class FrozenDict(dict): pass

@dataclass
class StateUpdate:
    """
    Represents a requested update to the Context State.
    Can be returned by a Process to request a CAS commit.
    """
    key: Optional[str] = None
    val: Optional[Any] = None
    data: Optional[Dict[str, Any]] = None
    heavy: Optional[Dict[str, Any]] = None
    signal: Optional[Dict[str, Any]] = None
    assert_version: Optional[int] = None

@dataclass
class FunctionResult:
    """Wrapper for Rust Function Result."""
    val: Any = None
    key: Optional[str] = None


class ManagedAllocator:
    """
    Python-side Managed Memory Allocator for Zero-Copy Parallelism.
    Wraps multiprocessing.shared_memory with NumPy integration.
    Uses MemoryRegistry for lifecycle tracking (Zombie Recovery).
    """
    def __init__(self, capacity_mb: int = 512, session_id: str = None):
        import uuid
        import os
        
        self._session_id = session_id or f"theus_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        self._allocations = {}  # name -> SharedMemory
        self._capacity_bytes = capacity_mb * 1024 * 1024
        self._used_bytes = 0
        
        # Connect to Rust Registry for lifecycle tracking
        try:
            from theus_core.shm import MemoryRegistry
            self._registry = MemoryRegistry(self._session_id)
        except ImportError:
            self._registry = None
    
    def alloc(self, name: str, shape: tuple, dtype) -> Any:
        """
        Allocate a managed shared memory block.
        Returns a NumPy array backed by SharedMemory.
        """
        import numpy as np
        from multiprocessing.shared_memory import SharedMemory
        
        # Calculate size
        dtype = np.dtype(dtype)
        size = int(np.prod(shape) * dtype.itemsize)
        
        if self._used_bytes + size > self._capacity_bytes:
            raise MemoryError(f"ManagedAllocator capacity exceeded ({self._used_bytes + size} > {self._capacity_bytes})")
        
        # Create unique SHM name
        shm_name = f"theus_{self._session_id}_{name}"
        
        # Create SharedMemory
        shm = SharedMemory(name=shm_name, create=True, size=size)
        self._allocations[name] = shm
        self._used_bytes += size
        
        # Log to registry
        if self._registry:
            self._registry.log_allocation(shm_name, size)
        
        # Return NumPy view as ShmArray (subclass to hold shm ref)
        class ShmArray(np.ndarray):
            """NumPy array backed by SharedMemory."""
            pass
        
        arr = ShmArray(shape, dtype=dtype, buffer=shm.buf)
        arr._shm_ref = shm  # Store as class attribute
        return arr
    
    def get(self, name: str, shape: tuple = None, dtype = None) -> Any:
        """Get existing shared memory by name (for worker processes)."""
        from multiprocessing.shared_memory import SharedMemory
        
        shm_name = f"theus_{self._session_id}_{name}"
        
        if name in self._allocations:
            shm = self._allocations[name]
        else:
            shm = SharedMemory(name=shm_name, create=False)
            self._allocations[name] = shm
        
        if shape and dtype:
            import numpy as np
            dtype = np.dtype(dtype)
            arr = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
            arr._shm = shm
            return arr
        return shm
    
    def cleanup(self):
        """Release all managed memory."""
        for name, shm in self._allocations.items():
            try:
                shm.close()
                shm.unlink()
            except Exception:
                pass
        self._allocations.clear()
        self._used_bytes = 0
        
        if self._registry:
            self._registry.cleanup()
    
    def __del__(self):
        self.cleanup()


__all__ = ["State", "FrozenDict", "ContextError", "StateUpdate", "FunctionResult", "ManagedAllocator"]

