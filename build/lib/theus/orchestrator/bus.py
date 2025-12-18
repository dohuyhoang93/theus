import queue
import logging
from typing import Any, Optional

logger = logging.getLogger("SignalBus")

class SignalBus:
    """
    Thread-safe communication channel between GUI (Main Thread) and Workers (Theus Threads).
    Concept:
    - Main Thread puts User Actions ('CMD_SCAN') -> Bus.
    - Worker Thread puts Results ('EVT_DONE') -> Bus.
    """
    def __init__(self):
        self._queue = queue.Queue()
    
    def emit(self, signal: Any):
        """Send a signal."""
        # logger.debug(f"Signal Emitted: {signal}")
        self._queue.put(signal)
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Receive a signal."""
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def empty(self) -> bool:
        return self._queue.empty()
    
    def qsize(self) -> int:
        return self._queue.qsize()
