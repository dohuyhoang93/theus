from dataclasses import dataclass, field
from typing import Optional, Any
from .locks import LockManager

@dataclass
class LockedContextMixin:
    """
    Mixin that hooks __setattr__ to enforce LockManager policy.
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

