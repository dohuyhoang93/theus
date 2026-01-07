from typing import List, Optional, Callable, Dict
import functools
import inspect
import traceback

class ContractViolationError(Exception):
    """Raised when a Process violates its declared POP Contract."""
    pass

class ProcessContract:
    def __init__(self, inputs: List[str], outputs: List[str], side_effects: List[str] = None, errors: List[str] = None):
        self.inputs = inputs
        self.outputs = outputs
        self.side_effects = side_effects or []
        self.errors = errors or []

def process(inputs: List[str], outputs: List[str], side_effects: List[str] = None, errors: List[str] = None):
    """
    Decorator để định nghĩa một POP Process với I/O Contract rõ ràng.
    """
    def decorator(func: Callable):
        func._pop_contract = ProcessContract(inputs, outputs, side_effects, errors)
        
        # Pre-compute signature parameters
        sig = inspect.signature(func)
        valid_params = set(sig.parameters.keys())
        
        @functools.wraps(func)
        def wrapper(system_ctx, *args, **kwargs):
            # 1. Kwargs Filtering (Convenience for messy args)
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            
            # If func accepts **kwargs, pass all
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                filtered_kwargs = kwargs
            
            try:
                return func(system_ctx, *args, **filtered_kwargs)
            except Exception as e:
                # DEBUG: Log traceback
                try:
                    with open("debug_trace.txt", "a") as f:
                        f.write(f"ERROR in {func.__name__}:\n")
                        traceback.print_exc(file=f)
                except:
                    pass
                raise e
        return wrapper
    return decorator
