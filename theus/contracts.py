from typing import List, Optional, Callable, Dict
import functools
import inspect
from enum import Enum
try:
    from theus_core import OutboxMsg
except ImportError:
    class OutboxMsg:
        def __init__(self, topic, payload): pass

class ContractViolationError(Exception):
    """Raised when a Process violates its declared POP Contract."""
    pass

class SemanticType(str, Enum):
    PURE = "pure"
    EFFECT = "effect"
    GUIDE = "guide"

class ProcessContract:
    def __init__(self, inputs: List[str], outputs: List[str], semantic: SemanticType = SemanticType.PURE, errors: List[str] = None, side_effects: List[str] = None, parallel: bool = False):
        self.inputs = inputs
        self.outputs = outputs
        self.semantic = semantic
        self.errors = errors or []
        self.side_effects = side_effects or []
        self.parallel = parallel

def process(inputs: List[str] = None, outputs: List[str] = None, semantic: SemanticType = SemanticType.EFFECT, errors: List[str] = None, side_effects: List[str] = None, parallel: bool = False):
    # Support bare decorator usage @process
    if callable(inputs):
        func = inputs
        # Reset args to defaults
        inputs = []
        outputs = []
        semantic = SemanticType.EFFECT
        errors = []
        
        # Apply logic immediately
        func._pop_contract = ProcessContract(inputs, outputs, semantic, errors, side_effects, parallel)
        
        sig = inspect.signature(func)
        valid_params = set(sig.parameters.keys())
        
        def filter_kwargs(kwargs):
            filtered = {k: v for k, v in kwargs.items() if k in valid_params}
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                filtered = kwargs
            return filtered

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    return await func(system_ctx, *args, **filtered_kwargs)
                except Exception as e:
                    raise e
            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    return func(system_ctx, *args, **filtered_kwargs)
                except Exception as e:
                    raise e
            return wrapper

    # Normal factory usage @process(...)
    inputs = inputs or []
    outputs = outputs or []
    
    def decorator(func: Callable):
        func._pop_contract = ProcessContract(inputs, outputs, semantic, errors, side_effects, parallel)
        
        # Pre-compute signature parameters
        sig = inspect.signature(func)
        valid_params = set(sig.parameters.keys())
        
        def filter_kwargs(kwargs):
            # 1. Kwargs Filtering (Convenience for messy args)
            filtered = {k: v for k, v in kwargs.items() if k in valid_params}
            
            # If func accepts **kwargs, pass all
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                filtered = kwargs
            return filtered

        # Check if async
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    return await func(system_ctx, *args, **filtered_kwargs)
                except Exception as e:
                    # Log logic if needed
                    raise e
            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(system_ctx, *args, **kwargs):
                filtered_kwargs = filter_kwargs(kwargs)
                try:
                    return func(system_ctx, *args, **filtered_kwargs)
                except Exception as e:
                    raise e
            return wrapper

    return decorator
