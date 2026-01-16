try:
    from theus_core import WorkflowEngine as WorkflowEngineRust
except ImportError:
    class WorkflowEngineRust:
        def __init__(self, config): pass
        def simulate(self, ctx): return []

class WorkflowEngine(WorkflowEngineRust):
    pass

__all__ = ["WorkflowEngine"]
