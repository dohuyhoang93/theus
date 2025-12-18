from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional
from ..interfaces import IScheduler

class ThreadExecutor(IScheduler):
    """
    Implements concurrency via a fixed ThreadPool.
    Why?
    1. Prevents OS resource exhaustion (max_workers).
    2. Allows blocking code (time.sleep) to run without freezing Main Thread (GUI).
    3. Python GIL limits CPU parallelism, but fine for IO/Latency simulation.
    """
    def __init__(self, max_workers: int = 4):
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="TheusWorker")
        
    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """
        Submit a task to the pool. Returns a standard concurrent.futures.Future.
        """
        return self._pool.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True):
        self._pool.shutdown(wait=wait)
