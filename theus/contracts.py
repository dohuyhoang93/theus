from typing import List, Callable
import functools
import inspect
from enum import Enum

try:
    from theus_core import OutboxMsg
except ImportError:

    class OutboxMsg:
        def __init__(self, topic, payload):
            pass


class ContractViolationError(Exception):
    """Raised when a Process violates its declared POP Contract."""

    pass


def _normalize_multi_output_return(result, func_name: str, outputs: List[str]):
    """
    Enforce explicit return contract for multi-output processes.

    Rule:
      - None        → OK: proxy mutations are the sole source of truth
      - tuple/list  → OK: unpack positionally onto declared outputs
      - dict        → OK: map by key onto declared outputs
      - scalar      → ContractViolationError (str, int, float, bool, etc.)
                      A scalar return for a multi-output process is always
                      ambiguous — it cannot be mapped to N paths without
                      guessing. Use return None for proxy-only processes.
    """
    if len(outputs) <= 1:
        return result
    if result is None or isinstance(result, (tuple, list, dict)):
        return result
    # Scalar return with multiple declared outputs — contract violation
    raise ContractViolationError(
        f"Process '{func_name}' declares {len(outputs)} outputs {outputs!r} "
        f"but returned a single {type(result).__name__!r} value ({result!r}).\n"
        f"  Multi-output processes must return one of:\n"
        f"    • None               — proxy mutations are sole source of truth\n"
        f"    • {len(outputs)}-tuple/list       — positional: (val_0, val_1, ...)\n"
        f"    • dict               — by key: {{\"output.path\": val, ...}}\n"
        f"  Got: {result!r}"
    )


class SemanticType(str, Enum):
    PURE = "pure"
    EFFECT = "effect"
    GUIDE = "guide"


class ProcessContract:
    def __init__(
        self,
        inputs: List[str],
        outputs: List[str],
        semantic: SemanticType = SemanticType.PURE,
        errors: List[str] = None,
        side_effects: List[str] = None,
        parallel: bool = False,
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.semantic = semantic
        self.errors = errors or []
        self.side_effects = side_effects or []
        self.parallel = parallel


class AdminTransaction:
    """
    [RFC-001] Context Manager to elevate context permissions (Admin Mode).
    Bypasses Zone Physics (e.g. allows deleting from Log Zone).
    """

    def __init__(self, ctx):
        self.ctx = ctx

    def __enter__(self):
        # print(f"DEBUG: AdminTransaction.__enter__ called for {type(self.ctx)}")
        if hasattr(self.ctx, "_elevate"):
             self.ctx._elevate(True)
        return self.ctx

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.ctx, "_elevate"):
             self.ctx._elevate(False)


def process(
    inputs: List[str] = None,
    outputs: List[str] = None,
    semantic: SemanticType = SemanticType.EFFECT,
    errors: List[str] = None,
    side_effects: List[str] = None,
    parallel: bool = False,
):
    # Support bare decorator usage @process
    if callable(inputs):
        func = inputs
        # Reset args to defaults
        inputs = []
        outputs = []
        semantic = SemanticType.EFFECT
        errors = []

        # Apply logic immediately
        func._pop_contract = ProcessContract(
            inputs, outputs, semantic, errors, side_effects, parallel
        )

        sig = inspect.signature(func)
        valid_params = set(sig.parameters.keys())

        def filter_kwargs(kwargs):
            filtered = {k: v for k, v in kwargs.items() if k in valid_params}
            if any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                filtered = kwargs
            return filtered

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    result = await func(system_ctx, *args, **filtered_kwargs)
                    return _normalize_multi_output_return(result, func.__name__, outputs)
                except Exception as e:
                    raise e
            
            # [FIX] Copy contract to wrapper
            wrapper._pop_contract = func._pop_contract
            return wrapper
        else:

            @functools.wraps(func)
            def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    result = func(system_ctx, *args, **filtered_kwargs)
                    return _normalize_multi_output_return(result, func.__name__, outputs)
                except Exception as e:
                    raise e
            
            # [FIX] Copy contract to wrapper
            wrapper._pop_contract = func._pop_contract
            return wrapper

    # Normal factory usage @process(...)
    inputs = inputs or []
    outputs = outputs or []

    def decorator(func: Callable):
        func._pop_contract = ProcessContract(
            inputs, outputs, semantic, errors, side_effects, parallel
        )

        # Pre-compute signature parameters
        sig = inspect.signature(func)
        valid_params = set(sig.parameters.keys())

        def filter_kwargs(kwargs):
            # 1. Kwargs Filtering (Convenience for messy args)
            filtered = {k: v for k, v in kwargs.items() if k in valid_params}

            # If func accepts **kwargs, pass all
            if any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                filtered = kwargs
            return filtered

        # Check if async
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    result = await func(system_ctx, *args, **filtered_kwargs)
                    return _normalize_multi_output_return(result, func.__name__, outputs)
                except Exception as e:
                    raise e

            # [FIX] Copy contract to wrapper
            wrapper._pop_contract = func._pop_contract
            return wrapper
        else:

            @functools.wraps(func)
            def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    result = func(system_ctx, *args, **filtered_kwargs)
                    return _normalize_multi_output_return(result, func.__name__, outputs)
                except Exception as e:
                    raise e

            # [FIX] Copy contract to wrapper
            wrapper._pop_contract = func._pop_contract
            return wrapper

    return decorator
