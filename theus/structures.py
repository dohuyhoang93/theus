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

__all__ = ["State", "FrozenDict", "ContextError", "StateUpdate"]
