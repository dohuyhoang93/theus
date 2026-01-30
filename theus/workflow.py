from typing import TYPE_CHECKING

# [DX] Theus v3 requires Rust Core. Fail fast if missing.
try:
    from theus_core import WorkflowEngine as _RustWorkflowEngine
except ImportError as e:
    raise ImportError(
        "CRITICAL: Could not import 'theus_core'. Theus v3 requires the Rust extension.\n"
        "Please ensure it is installed correctly via 'pip install .'"
    ) from e

if TYPE_CHECKING:

    class WorkflowEngine(_RustWorkflowEngine):
        """
        Theus Flux Engine (Rust-Backed).
        Executes Workflow YAML with high-performance state machine logic.
        """

        def __init__(
            self, yaml_content: str, max_ops: int = 10000, debug: bool = False
        ): ...
        def execute(self, ctx: dict, executor_callback: callable) -> list: ...
        def step(self, ctx: dict) -> list: ...
else:
    WorkflowEngine = _RustWorkflowEngine

__all__ = ["WorkflowEngine"]
