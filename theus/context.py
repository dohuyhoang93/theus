from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict
from .locks import LockManager
from .zones import ContextZone, resolve_zone


@dataclass(frozen=True)
class NamespacePolicy:
    """[RFC-002] Security policy for a specific Namespace."""
    allow_read: bool = True
    allow_update: bool = True
    allow_delete: bool = False
    allow_append: bool = True
    
    def to_caps(self) -> int:
        """Convert policy to Rust-compatible bitmask."""
        caps = 0
        if self.allow_read: caps |= 1    # CAP_READ
        if self.allow_update: caps |= 2  # CAP_UPDATE
        if self.allow_append: caps |= 4  # CAP_APPEND
        if self.allow_delete: caps |= 8  # CAP_DELETE
        return caps


class NamespaceRegistry:
    """[RFC-002] Central Registry for Theus Namespaces."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NamespaceRegistry, cls).__new__(cls)
            cls._instance._namespaces = {}
        return cls._instance

    def register(self, name: str, policy: NamespacePolicy = None, default_data: Any = None):
        """Register a new isolation namespace."""
        if policy is None:
            policy = NamespacePolicy()
        self._namespaces[name] = {
            "policy": policy,
            "data": default_data if default_data is not None else {}
        }

    def get_policy(self, name: str) -> NamespacePolicy:
        """Retrieve policy for a namespace, fallback to default."""
        if name in self._namespaces:
             return self._namespaces[name]["policy"]
        return NamespacePolicy()

    def resolve_path(self, path: str) -> tuple[str, str]:
        """Split 'namespace.key' into ('namespace', 'key')."""
        parts = path.split(".", 1)
        if len(parts) == 2 and parts[0] in self._namespaces:
            return parts[0], parts[1]
        return "default", path

    def get_all_data(self) -> dict:
        """Collect and merge data from all namespaces for core hydration."""
        compiled = {}
        for name, ns in self._namespaces.items():
            data = ns.get("data", {})
            
            # Unpack default namespace into root
            if name == "default":
                if isinstance(data, dict):
                    compiled.update(data)
                elif hasattr(data, "to_dict"):
                    compiled.update(data.to_dict())
                elif hasattr(data, "model_dump"):
                    compiled.update(data.model_dump())
                elif hasattr(data, "dict"): # Pydantic v1
                    compiled.update(data.dict())
                elif hasattr(data, "__dict__"):
                    compiled.update(vars(data))
            else:
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                elif hasattr(data, "model_dump"):
                    data = data.model_dump()
                elif hasattr(data, "dict"):
                    data = data.dict()
                compiled[name] = data
        return compiled

    def clear(self):
        """Reset registry (mainly for testing)."""
        self._namespaces.clear()


class Namespace:
    """
    [RFC-001/002] Declarative Namespace helper.
    Functions as a Descriptor to provide dynamic context instances.
    """
    def __init__(self, context_cls: type, policy: NamespacePolicy = None):
        self.context_cls = context_cls
        self.policy = policy
        self._name = None
        
    def __set_name__(self, owner, name):
        self._name = name
        registry = NamespaceRegistry()
        registry.register(name, policy=self.policy)
        
    def __get__(self, instance, owner):
        if instance is None:
            return self
            
        # Lazy initialization of the namespace context instance
        attr_name = f"_ns_inst_{self._name}"
        if not hasattr(instance, attr_name):
            setattr(instance, attr_name, self.context_cls())
        return getattr(instance, attr_name)


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
            raise PermissionError(
                "Access Denied: Only the Owner process can unlink Managed Memory."
            )

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
            if obj is None:
                return
            self.shm = getattr(obj, "shm", None)

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
        if hasattr(val, "name") and hasattr(val, "dtype") and hasattr(val, "shape"):
            # Lazy Import to avoid overhead if not used
            try:
                import numpy as np
                from multiprocessing import shared_memory
            except ImportError:
                return val  # Fallback if numpy not present? Or raise?

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

    def __getattr__(self, name):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'HeavyZoneWrapper' object has no attribute '{name}'")

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
            exclude_zones = [
                ContextZone.SIGNAL,
                ContextZone.META,
                ContextZone.HEAVY,
                ContextZone.LOG,
            ]

        data = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue

            zone = self.get_zone(k)
            if zone in exclude_zones:
                continue

            if hasattr(v, "to_dict"):
                data[k] = v.to_dict(exclude_zones)
            else:
                data[k] = v

        return data

    def from_dict(self, data: Dict[str, Any]):
        """
        Load state from dictionary.
        """
        for k, v in data.items():
            if k.startswith("_"):
                continue

            if hasattr(self, k):
                current_val = getattr(self, k)
                if hasattr(current_val, "from_dict") and isinstance(v, dict):
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
    Supports Dynamic Namespace Resolution [RFC-002].
    """

    global_ctx: Optional[BaseGlobalContext] = field(default=None)
    domain: Optional[BaseDomainContext] = field(default=None)

    def to_dict(self, exclude_zones: List[ContextZone] = None) -> Dict[str, Any]:
        """
        [RFC-002] Overridden to include both fields and Namespaces.
        """
        data = {}
        
        # 1. Manual Unpacking of known fields (since Mixin lacks to_dict)
        if hasattr(self, "domain") and self.domain is not None:
            data["domain"] = self.domain.to_dict(exclude_zones) if hasattr(self.domain, "to_dict") else self.domain
        if hasattr(self, "global_ctx") and self.global_ctx is not None:
             g = self.global_ctx
             data["global"] = g.to_dict(exclude_zones) if hasattr(g, "to_dict") else g

        # 2. Add all registered Namespaces
        registry = NamespaceRegistry()
        for ns_name in registry._namespaces:
            if ns_name == "default": continue
                
            if ns_name not in data:
                # Access via attribute to trigger descriptor/lazy-init
                ns_inst = getattr(self, ns_name, None)
                if ns_inst is not None:
                     if hasattr(ns_inst, "to_dict"):
                        data[ns_name] = ns_inst.to_dict(exclude_zones)
                     elif hasattr(ns_inst, "model_dump"):
                        data[ns_name] = ns_inst.model_dump()
                     else:
                        data[ns_name] = ns_inst
                    
        return data

    def __getattr__(self, name: str) -> Any:
        # 1. Bypass internal fields
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        # 2. [RFC-002] Dynamic Namespace Fallback
        # If accessing an attribute that doesn't exist on SystemContext, 
        # check if it's a registered Namespace.
        registry = NamespaceRegistry()
        if name in registry._namespaces:
            # We assume the engine has hydrated this into the state.
            # In production, this call usually happens through ContextGuard,
            # but providing a fallback here helps with local testing/REPL.
            if hasattr(self, "_state"):
                return self._state.data.get(name)
            
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


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
        self._allocations = {}  # name -> (shm, shm_array, creator_pid)
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

                    if hasattr(theus_core, "shm") and hasattr(
                        theus_core.shm, "MemoryRegistry"
                    ):
                        MemoryRegistry = theus_core.shm.MemoryRegistry
                    elif hasattr(theus_core, "theus_core") and hasattr(
                        theus_core.theus_core, "shm"
                    ):
                        # Wrapper case
                        MemoryRegistry = theus_core.theus_core.shm.MemoryRegistry
                    else:
                        # Last ditch: try importing shm
                        from theus_core.shm import MemoryRegistry

            self._registry = MemoryRegistry(self._session_id)  # Scans zombies on init
        except (ImportError, AttributeError, NameError) as e:
            # Fallback for dev/test without compiling
            print(
                f"[Theus] Warning: Rust Core MemoryRegistry not found. Zombie Collection disabled. Error: {e}"
            )
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
        if self._cleaned:
            return

        current_pid = os.getpid()

        # 1. Python Cleanup (Close handles)
        for name, (shm, _, creator_pid) in self._allocations.items():
            try:
                shm.close()  # Always close handle

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


class Mutable:
    """
    Semantic marker for the POP Linter and Zone Physics. 
    Indicates that a field is intended to be mutable despite its prefix.
    """
    pass

class AppendOnly:
    """
    Semantic marker for the POP Linter and Zone Physics.
    Restricts a field to Append-Only operations (CAP_READ | CAP_APPEND).
    """
    pass

class Immutable:
    """
    Semantic marker for the POP Linter and Zone Physics.
    Restricts a field to Read-Only operations (CAP_READ).
    """
    pass

# [RFC-001 §7] Python-side mirror of Rust PHYSICS_OVERRIDES.
# Populated by engine.py during _parse_physics_overrides().
# Queried by guards.py _check_zone_physics() to respect Annotated overrides.
PYTHON_PHYSICS_OVERRIDES: dict[str, int] = {}
