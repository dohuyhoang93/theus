from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict
from .locks import LockManager
from .zones import ContextZone, resolve_zone

@dataclass
class TransactionError(Exception):
    pass

try:
    import numpy as np
    from multiprocessing import shared_memory

    class SafeSharedMemory:
        """
        Proxy for SharedMemory that forbids unlink() to enforce strict ownership.
        Used by Borrower processes.
        """
        def __init__(self, name):
            self._shm = shared_memory.SharedMemory(name=name)
            self.name = self._shm.name
            self.size = self._shm.size
            self.buf = self._shm.buf
            
        def close(self):
            return self._shm.close()
            
        def unlink(self):
            raise PermissionError("Access Denied: Only the Owner process can unlink Managed Memory.")
            
        def __getattr__(self, name):
            return getattr(self._shm, name)

    def rebuild_shm_array(name, shape, dtype):
        """Helper to reconstruct ShmArray from pickle meta-data."""
        try:
            # v3.2 Strict Mode: Borrowers get SafeSharedMemory
            shm = SafeSharedMemory(name=name)
        except FileNotFoundError:
            # If SHM is gone, return None or empty?
            # For now return None to indicate failure
            return None
        
        # Zero-Copy Re-attach
        raw_arr = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        return ShmArray(raw_arr, shm=shm)

    class ShmArray(np.ndarray):
        """Numpy Array that keeps the backing SharedMemory object alive."""
        def __new__(cls, input_array, shm=None):
            obj = np.asarray(input_array).view(cls)
            obj.shm = shm
            return obj

        def __array_finalize__(self, obj):
            if obj is None: return
            self.shm = getattr(obj, 'shm', None)
            
        def __reduce__(self):
            """Smart Pickling: Send metadata, not data."""
            if self.shm is None:
                # Fallback to standard pickle if no SHM backing
                return super().__reduce__()
            
            # Send (Function, Args) tuple
            return (rebuild_shm_array, (self.shm.name, self.shape, self.dtype))

except ImportError:
    np = None
    ShmArray = None
    rebuild_shm_array = None

class HeavyZoneWrapper:
    """
    Smart Wrapper for ctx.heavy that handles Zero-Copy interactions.
    If it sees a BufferDescriptor, it auto-converts to memoryview/numpy.
    """
    def __init__(self, data_dict):
        self._data = data_dict

    def __getitem__(self, key):
        val = self._data[key]
        # Check if it's a BufferDescriptor (duck typing or strict check)
        if hasattr(val, 'name') and hasattr(val, 'dtype') and hasattr(val, 'shape'):
             # Lazy Import to avoid overhead if not used
             try:
                 import numpy as np
                 from multiprocessing import shared_memory
             except ImportError:
                 return val # Fallback if numpy not present? Or raise?
             
             # Rehydrate View
             try:
                 shm = shared_memory.SharedMemory(name=val.name)
                 # Note: This is read-only view logic for now
                 # We need to ensure we don't leak SHM handles. 
                 # Python's SharedMemory automatic cleanup is tricky. 
                 # Ideally, we should cache this SHM handle handle.
                 raw_arr = np.ndarray(val.shape, dtype=val.dtype, buffer=shm.buf)
                 # Wrap in ShmArray to keep 'shm' alive
                 return ShmArray(raw_arr, shm=shm)
             except FileNotFoundError:
                 # SHM might be gone
                 return None
        return val
    
    def __setitem__(self, key, value):
        # Write-Through to underlying dict (Transaction Logic handles the rest)
        self._data[key] = value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
            
    def __contains__(self, key):
        return key in self._data

    def items(self):
        for k in self._data:
            yield k, self[k]
            
    def __repr__(self):
        return f"<HeavyZoneWrapper keys={list(self._data.keys())}>"

@dataclass
class LockedContextMixin:
    """
    Mixin that hooks __setattr__ to enforce LockManager policy.
    Now also supports Zone-aware Persistence (to_dict/from_dict).
    """
    _lock_manager: Optional[LockManager] = field(default=None, repr=False, init=False)

    def set_lock_manager(self, manager: LockManager):
        object.__setattr__(self, "_lock_manager", manager)

    def __setattr__(self, name: str, value: Any):
        # 1. Bypass internal fields
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        # 2. Check Lock Manager
        # Use object.__getattribute__ to avoid recursion? No, self._lock_manager is safe if set via object.__setattr__
        # But accessing self._lock_manager inside __setattr__ might trigger __getattr__ loop if not careful?
        # Standard access is fine.
        mgr = getattr(self, "_lock_manager", None)
        if mgr:
            mgr.validate_write(name, self)
            
        # 3. Perform Write
        super().__setattr__(name, value)

    def get_zone(self, key: str) -> ContextZone:
        """
        Resolve the semantic zone of a key.
        """
        return resolve_zone(key)

    @property
    def heavy(self):
        # Auto-Dispatch for Zero-Copy
        return HeavyZoneWrapper(self._state.heavy)

    def restrict_view(self):
        """
        Return the underlying state object for Read-Only wrapping.
        Used by Engine to create RestrictedStateProxy for PURE processes.
        """
        return self._state

    def to_dict(self, exclude_zones: List[ContextZone] = None) -> Dict[str, Any]:
        """
        Export context state to dictionary, filtering out specified zones.
        Default exclusion: SIGNAL, META, HEAVY (if not specified).
        """
        if exclude_zones is None:
            exclude_zones = [ContextZone.SIGNAL, ContextZone.META, ContextZone.HEAVY]
            
        data = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"): continue
            
            zone = self.get_zone(k)
            if zone in exclude_zones:
                continue
                
            if hasattr(v, 'to_dict'):
                data[k] = v.to_dict(exclude_zones)
            else:
                data[k] = v
                
        return data

    def from_dict(self, data: Dict[str, Any]):
        """
        Load state from dictionary.
        """
        for k, v in data.items():
            if k.startswith("_"): continue
            
            if hasattr(self, k):
                current_val = getattr(self, k)
                if hasattr(current_val, 'from_dict') and isinstance(v, dict):
                    current_val.from_dict(v)
                else:
                    setattr(self, k, v)
            else:
                setattr(self, k, v)


@dataclass
class BaseGlobalContext(LockedContextMixin):
    """
    Base Class cho Global Context (Immutable/Locked).
    """
    pass

@dataclass
class BaseDomainContext(LockedContextMixin):
    """
    Base Class cho Domain Context (Mutable/Locked).
    """
    pass

@dataclass
class BaseSystemContext(LockedContextMixin):
    """
    Base Class cho System Context (Wrapper).
    """
    global_ctx: BaseGlobalContext
    domain: BaseDomainContext
    
import uuid
import atexit
import os

import json
import signal
import time

REGISTRY_FILE = ".theus_memory_registry.jsonl"

class HeavyZoneAllocator:
    """
    Manager for Shared Memory Lifecycle (v3.1).
    Delegates to Rust Core (v3.2) for Registry and Zombie Collection.
    Fork-Safe: Tracks creator PID for each segment.
    """
    def __init__(self):
        self._session_id = str(uuid.uuid4())[:8]
        # self._pid is legacy/reference, we use os.getpid() dynamically now
        self._allocations = {} # name -> (shm, shm_array, creator_pid)
        self._cleaned = False
        
        # v3.2 Rust Core Integration
        try:
            # Strategy 1: Direct Import
            try:
                from theus_core import MemoryRegistry
            except ImportError:
                 # Strategy 2: Nested Extension Import
                 try:
                     from theus_core.theus_core import MemoryRegistry
                 except ImportError:
                     # Strategy 3: Submodule via Attribute Access (Reliable for PyO3)
                     import theus_core
                     if hasattr(theus_core, 'shm') and hasattr(theus_core.shm, 'MemoryRegistry'):
                         MemoryRegistry = theus_core.shm.MemoryRegistry
                     elif hasattr(theus_core, 'theus_core') and hasattr(theus_core.theus_core, 'shm'):
                          # Wrapper case
                          MemoryRegistry = theus_core.theus_core.shm.MemoryRegistry
                     else:
                          # Last ditch: try importing shm
                          from theus_core.shm import MemoryRegistry

            self._registry = MemoryRegistry(self._session_id) # Scans zombies on init
        except (ImportError, AttributeError, NameError) as e:
            # Fallback for dev/test without compiling
            print(f"[Theus] Warning: Rust Core MemoryRegistry not found. Zombie Collection disabled. Error: {e}")
            self._registry = None
        
        atexit.register(self.cleanup)

    def alloc(self, key: str, shape: tuple, dtype) -> Any:
        """
        Allocate a managed ShmArray.
        Name format: theus:{session}:{pid}:{key}
        """
        if np is None:
            raise ImportError("Numpy/SharedMemory not available")

        current_pid = os.getpid()
        
        # 1. Resolve Namespace (Dynamic PID to prevent collision in forks)
        full_name = f"theus:{self._session_id}:{current_pid}:{key}"
        
        # 2. Calculate Size
        temp = np.dtype(dtype)
        size = int(np.prod(shape) * temp.itemsize)

        # 3. Alloc (Collision Safe via Python SharedMemory)
        try:
            shm = shared_memory.SharedMemory(create=True, size=size, name=full_name)
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=full_name)
        
        # 4. Wrap & Track
        raw_arr = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        
        # Safe Wrapper
        arr = ShmArray(raw_arr, shm=shm)
        
        self._allocations[full_name] = (shm, arr, current_pid)
        
        # 5. Notify Rust Registry
        if self._registry:
            self._registry.log_allocation(full_name, size)
        
        return arr

    def cleanup(self):
        """
        Destructor ensuring UNLINK is called.
        Fork-Safe: Only unlinks segments created by THIS process.
        """
        if self._cleaned: return
        
        current_pid = os.getpid()
        
        # 1. Python Cleanup (Close handles)
        for name, (shm, _, creator_pid) in self._allocations.items():
            try:
                shm.close() # Always close handle
                
                if creator_pid == current_pid:
                    # We are the owner. Unlink.
                    shm.unlink()
            except Exception:
                pass
        
        # 2. Rust Cleanup
        # Registry handles persistent file updates if needed
        
        self._allocations.clear()
        self._cleaned = True
    
    def __del__(self):
        self.cleanup()

