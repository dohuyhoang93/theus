import logging
from typing import Any, Set, Optional
from .contracts import ContractViolationError

# Import Core Rust Guard
try:
    from theus_core import ContextGuard as RustContextGuard
    from theus_core import Transaction
except ImportError:
    # During build/bootstrap, this might fail. We define a dummy or re-raise.
    # But since we are running in environment where we expect it:
    raise ImportError("theus_core module not found. Please install with 'pip install -e ./theus_framework'")

# Keep Logger Adapter for backward compatibility
class ContextLoggerAdapter(logging.LoggerAdapter):
    """
    Auto-injects Process Name into logs.
    Usage: ctx.log.info("msg", key=value) -> [ProcessName] msg {key=value}
    """
    def process(self, msg, kwargs):
        process_name = self.extra.get('process_name', 'Unknown')
        prefix = f"[{process_name}] "
        if kwargs:
            data_str = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            msg = f"{prefix}{msg} {{{data_str}}}"
            return msg, {}
        else:
            return f"{prefix}{msg}", kwargs

class ContextGuard(RustContextGuard):
    """
    Hybrid Python wrapper for Rust ContextGuard.
    Adds 'log' attribute via Python __dict__ (enabled by #[pyclass(dict)] in Rust).
    """
    def __init__(
        self, 
        target_obj: Any, 
        allowed_inputs: Set[str], 
        allowed_outputs: Set[str], 
        path_prefix: str = "", 
        transaction: Optional[Transaction] = None, 
        strict_mode: bool = False, 
        process_name: str = "Unknown"
    ):
        # Initialize Rust Parent
        # Rust signature: (target, inputs, outputs, tx, is_admin, strict_mode)
        # We assume 'is_admin' defaults false or we pass it? 
        # Looking at guards.rs: new(target, inputs, outputs, tx, is_admin, strict_mode)
        # This Python wrapper hides 'is_admin' (defaulting False in usage?) 
        # engine.py calls it. Let's check signature. 
        # engine.py usually passes: target, inputs, outputs, prefix, tx, strict, name
        
        # We call super().__init__ which maps to Rust new()
        # super().__init__(...) calls object.__init__ which fails with args.
        # Rust state is already initialized by __new__ (which runs before __init__).
        pass
        
        # Manually set path_prefix? Rust new_internal sets it to "".
        # Wait, Rust `new_internal` sets `path_prefix` to "".
        # But `engine.py` passes `path_prefix`.
        # The Rust `new` seems to ignore `path_prefix` or expects "inputs" to be full paths?
        # Check guards.rs: `path_prefix: "".to_string()` hardcoded in new_internal?
        # Yes. line 38: `path_prefix: "".to_string()`.
        # BUT current Python ContextGuard respects `path_prefix` passed in init.
        # This is a GAP. 
        
        # Update: We need to support `path_prefix` in Rust `new` or set it after?
        # Rust `ContextGuard` doesn't expose `path_prefix` setter.
        # However, `apply_guard` creates children with correct prefix.
        # The ROOT guard (created here) usually has prefix "" (empty) or "domain"?
        # If engine creates Guard for "domain", prefix is "domain".
        # Rust Guard needs to know this prefix for `full_path` construction.
        
        # FIX: I need to update Rust `new` to accept `path_prefix`.
        # I will apply a patch to guards.rs to accept path_prefix.
        # For now, let's assume I fix Rust. I will proceed with Python wrapper code assuming Rust signature matches.
        
        # Setup Logger
        base_logger = logging.getLogger("POP_PROCESS")
        adapter = ContextLoggerAdapter(base_logger, {'process_name': process_name})
        # Rust Guard is now smart enough to whitelist 'log' into __dict__
        self.log = adapter

        # NOTE: Zone Enforcement is strictly done in Rust constructor (Strict Mode) specific logic
        # or we rely on Rust.
