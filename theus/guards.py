import logging
from typing import Any, Set, Optional, TYPE_CHECKING
from .contracts import ContractViolationError

# [v3.1] Force Mandatory Rust Core
try:
    from theus_core import ContextGuard as _RustContextGuard
    from theus_core import Transaction
except ImportError as e:
    raise ImportError(
        "CRITICAL: 'theus_core' missing. Please install theus extension."
    ) from e

if TYPE_CHECKING:

    class ContextGuard(_RustContextGuard):
        """
        Zero-Trust Guard for Context Access.
        Wraps Rust implementation.
        """

        def __init__(
            self,
            target_obj: Any,
            allowed_inputs: Set[str],
            allowed_outputs: Set[str],
            path_prefix: str = "",
            transaction: Optional[Transaction] = None,
            strict_mode: bool = False,
            process_name: str = "Unknown",
        ): ...
        def get(self, path: str, default: Any = None) -> Any: ...
        def set(self, path: str, value: Any) -> None: ...
        def __getattr__(self, name: str) -> Any: ...
else:
    ContextGuard = _RustContextGuard


# Keep Logger Adapter for backward compatibility
class ContextLoggerAdapter(logging.LoggerAdapter):
    """
    Auto-injects Process Name into logs.
    Usage: ctx.log.info("msg", key=value) -> [ProcessName] msg {key=value}
    """

    def process(self, msg, kwargs):
        process_name = self.extra.get("process_name", "Unknown")
        prefix = f"[{process_name}] "
        if kwargs:
            data_str = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            msg = f"{prefix}{msg} {{{data_str}}}"
            return msg, {}
        else:
            return f"{prefix}{msg}", kwargs


class ContextGuard:
    """
    Zero-Trust Guard for Context Access (Python Wrapper via Composition).
    Wraps Rust implementation to provide Safe Access Control & Semantic Firewall.
    """

    def __init__(
        self,
        target_obj: Any,
        allowed_inputs: Set[str],
        allowed_outputs: Set[str],
        path_prefix: str = "",
        transaction: Optional[Transaction] = None,
        strict_guards: bool = False,
        process_name: str = "Unknown",
        _inner=None,  # Internal bypass
    ):
        if _inner:
            self._inner = _inner
        else:
            # Create Rust Core Guard
            # Rust signature: (target, inputs, outputs, path_prefix, tx, is_admin, strict_guards)
            self._inner = _RustContextGuard(
                target_obj,
                list(allowed_inputs),
                list(allowed_outputs),
                path_prefix,
                transaction,
                False,  # is_admin default
                strict_guards, # maps to strict_guards in Rust
            )

        # Setup Logger
        base_logger = logging.getLogger("POP_PROCESS")
        adapter = ContextLoggerAdapter(base_logger, {"process_name": process_name})
        self.log = adapter
        # Inject log into Rust side if supported (it is via pyclass dict)
        try:
            self._inner.log = adapter
        except AttributeError:
            pass

    def get(self, path: str, default: Any = None) -> Any:
        return self._inner.get(path, default)

    def set(self, path: str, value: Any) -> None:
        self._inner.set(path, value)

    def __getattr__(self, name: str) -> Any:
        val = getattr(self._inner, name)
        # If result is a Rust ContextGuard, wrap it again to maintain Python behavior
        if isinstance(val, _RustContextGuard):
            return ContextGuard(
                target_obj=None,
                allowed_inputs=set(),
                allowed_outputs=set(),  # Dummy
                _inner=val,
                process_name=self.log.extra.get("process_name", "Unknown"),
            )
        return val

    def __getitem__(self, key: Any) -> Any:
        val = self._inner[key]
        if isinstance(val, _RustContextGuard):
            return ContextGuard(
                target_obj=None,
                allowed_inputs=set(),
                allowed_outputs=set(),
                _inner=val,
                process_name=self.log.extra.get("process_name", "Unknown"),
            )
        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        self._inner[key] = value

    def __contains__(self, key: Any) -> bool:
        return key in self._inner

    def __iter__(self):
        return iter(self._inner)
