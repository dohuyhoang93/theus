from abc import ABC, abstractmethod
from typing import Any, List, Optional, Callable, Dict

class IEngine(ABC):
    """
    The Core Engine Interface.
    Responsibility: Safely execute a SINGLE atomic process.
    It does NOT know about workflows, loops, or events.
    """
    @abstractmethod
    def register_process(self, name: str, func: Callable) -> None:
        pass

    @abstractmethod
    def execute_process(self, process_name: str, context: Any) -> Any:
        """
        Execute a process synchronously and atomically.
        """
        pass
    
    @abstractmethod
    def get_process(self, name: str) -> Callable:
        pass

class IScheduler(ABC):
    """
    Concurrency Provider Interface.
    Responsibility: Run a function (usually engine.execute_process) in a thread/task.
    """
    @abstractmethod
    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """Return a Future-like object"""
        pass
    
    @abstractmethod
    def shutdown(self, wait: bool = True):
        pass

class IOrchestrator(ABC):
    """
    Workflow Manager Interface.
    Responsibility: Decide WHAT to run next (FSM, Loop, Chain).
    """
    @abstractmethod
    def run_workflow(self, workflow_name: str, context: Any) -> None:
        pass
