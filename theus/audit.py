from typing import List, Optional, TYPE_CHECKING
import sys

# [DX] Theus v3 requires Rust Core. Fail fast if missing.
try:
    from theus_core import AuditSystem as _RustAuditSystem
    from theus_core import AuditRecipe as _RustAuditRecipe
    from theus_core import AuditLogEntry, AuditLevel
    from theus_core import (
        AuditBlockError,
        AuditAbortError,
        AuditStopError,
        AuditWarning,
    )
except ImportError as e:
    raise ImportError(
        "CRITICAL: Could not import 'theus_core'. Theus v3 requires the Rust extension.\n"
        "Please ensure it is installed correctly via 'pip install .' or check your build environment."
    ) from e

if TYPE_CHECKING:

    class AuditRecipe(_RustAuditRecipe):
        """
        Configuration for the Audit System.
        Wraps Rust implementation.
        """

        def __init__(
            self,
            level: Optional[AuditLevel] = None,
            threshold_max: int = 3,
            threshold_min: int = 0,
            reset_on_success: bool = True,
        ): ...

    class AuditSystem(_RustAuditSystem):
        """
        Theus Audit System (Rust-Backed).
        Provides High-Performance Ring Buffer Logging and Schema Gatekeeping.
        """

        def log_fail(self, key: str) -> None:
            """Log a failure event. May raise AuditBlockError based on Level."""
            ...

        def log_success(self, key: str) -> None:
            """Log a success event. Resets failure counter if configured."""
            ...

        def get_count(self, key: str) -> int:
            """Get current failure count for a key."""
            ...

        def log(self, key: str, message: str) -> None:
            """Write a generic message to the Ring Buffer."""
            ...

        def get_logs(self) -> List[AuditLogEntry]:
            """Retrieve all logs from the Ring Buffer."""
            ...

        @property
        def ring_buffer_len(self) -> int:
            """Current number of entries in the Ring Buffer."""
            ...
else:
    AuditRecipe = _RustAuditRecipe
    AuditSystem = _RustAuditSystem

__all__ = [
    "AuditSystem",
    "AuditRecipe",
    "AuditLevel",
    "AuditLogEntry",
    "AuditBlockError",
    "AuditAbortError",
    "AuditStopError",
    "AuditWarning",
]
