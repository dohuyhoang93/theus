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
    HEAVY = "heavy"   # Large/External Objects (Log-only, no copy, audit via introspection)

# Prefix Definitions
PREFIX_SIGNAL: Final = ("sig_", "cmd_")
PREFIX_META: Final = ("meta_",)
PREFIX_HEAVY: Final = ("heavy_",)

def resolve_zone(key: str) -> ContextZone:
    """
    Determines the ContextZone of a variable based on its name prefix.
    
    Rules:
    - 'sig_*', 'cmd_*' -> SIGNAL
    - 'meta_*'         -> META
    - 'heavy_*'        -> HEAVY
    - Others           -> DATA
    """
    if key.startswith(PREFIX_SIGNAL):
        return ContextZone.SIGNAL
    
    if key.startswith(PREFIX_META):
        return ContextZone.META
    
    if key.startswith(PREFIX_HEAVY):
        return ContextZone.HEAVY
        
    return ContextZone.DATA

