from enum import Enum
from typing import Final

class ContextZone(Enum):
    """
    Defines the Semantic Zone of a context variable.
    See ADR-Hybrid-Context-Zones.
    """
    DATA = "data"     # Business State (Persistent, Auditable, Replayable)
    SIGNAL = "signal" # Transient Events/Commands (Ephemeral, No-Replay)
    META = "meta"     # Diagnostics/Observability (Read-Only for logic)

# Prefix Definitions
PREFIX_SIGNAL: Final = ("sig_", "cmd_")
PREFIX_META: Final = ("meta_",)

def resolve_zone(key: str) -> ContextZone:
    """
    Determines the ContextZone of a variable based on its name prefix.
    
    Rules:
    - 'sig_*', 'cmd_*' -> SIGNAL
    - 'meta_*'         -> META
    - Others           -> DATA
    """
    if key.startswith(PREFIX_SIGNAL):
        return ContextZone.SIGNAL
    
    if key.startswith(PREFIX_META):
        return ContextZone.META
        
    return ContextZone.DATA
