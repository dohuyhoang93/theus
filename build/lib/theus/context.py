from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict
from .locks import LockManager
from .zones import ContextZone, resolve_zone

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

    def to_dict(self, exclude_zones: List[ContextZone] = None) -> Dict[str, Any]:
        """
        Export context state to dictionary, filtering out specified zones.
        Default exclusion: SIGNAL, META (if not specified).
        """
        if exclude_zones is None:
            exclude_zones = [ContextZone.SIGNAL, ContextZone.META]
            
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
    domain_ctx: BaseDomainContext

