
try:
    import concurrent.interpreters as interpreters
    INTERPRETERS_SUPPORTED = True
except ImportError:
    interpreters = None
    INTERPRETERS_SUPPORTED = False

import queue
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future
from contextlib import contextmanager
import pickle
import multiprocessing

from theus.context import HeavyZoneWrapper

class ParallelContext:
    """Minimized Context for Parallel Execution (Picklable)"""
    def __init__(self, domain, heavy=None):
        self.domain = domain
        self._heavy = heavy

    @property
    def heavy(self):
        if self._heavy is None:
            return {}
        return HeavyZoneWrapper(self._heavy)

    @property
    def input(self):
        """Alias for domain (Inputs are merged into domain for Parallel Context)."""
        return self.domain

    def __getattr__(self, name):
        # Fallback for other attributes: Raise AttributeError to play nice with Pickle
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

class InterpreterPool:
    """
    Manages a pool of Python Sub-Interpreters for parallel execution.
    Uses 'concurrent.interpreters' (PEP 554) available in Python 3.14.
    """
    def __init__(self, size: int = 2):
        self._size = size
        self._pool = queue.Queue(maxsize=size)
        self._executor = ThreadPoolExecutor(max_workers=size, thread_name_prefix="TheusSubInterp")
        self._lock = threading.Lock()
        
        # Initialize interpreters
        # Note: Optimization - Lazy init or Eager? Eager for predictability.
        for i in range(size):
            try:
                interp = interpreters.create()
                self._pool.put(interp)
            except Exception as e:
                # Fallback if creation fails (platform support)
                print(f"Failed to create sub-interpreter {i}: {e}")
                # We should probably raise if requested size cannot be met or warn
                raise RuntimeError(f"Sub-interpreters not supported or failed to init: {e}")

    @property
    def size(self):
        return self._size



    def submit(self, func, *args, **kwargs) -> Future:
        """
        Submit a task to run in a sub-interpreter.
        Uses pickle to marshal function and arguments.
        """
        # Pickle the payload
        try:
            payload = pickle.dumps((func, args, kwargs))
        except Exception as e:
            f = Future()
            f.set_exception(e)
            return f
            
        return self._executor.submit(self._execute_wrapper, payload)

    def _execute_wrapper(self, payload):
        interp = self._pool.get(block=True)
        try:
            # Execute runner with pickled payload
            # bytes are shareable. 
            # Note: interp.call(_unpickle_runner, payload) passes payload as first arg.
            return interp.call(_unpickle_runner, payload)
        finally:
            self._pool.put(interp)

    def shutdown(self):
        self._executor.shutdown(wait=True)
        # Clean up interpreters
        while not self._pool.empty():
            interp = self._pool.get()
            try:
                # interp.close() exists? Yes according to dir()
                if hasattr(interp, "close"):
                    interp.close()
            except Exception:
                pass

class ProcessPool:
    """
    Backwards Compatible Pool that uses Multiprocessing (Spawn).
    Used when Sub-Interpreters are unavailable or incompatible (e.g. NumPy < 2.0).
    """
    def __init__(self, size: int = 2):
        self._size = size
        # Force spawn for consistent behavior across platforms (and Windows support)
        ctx = multiprocessing.get_context("spawn")
        self._executor = ProcessPoolExecutor(max_workers=size, mp_context=ctx)
        
    @property
    def size(self):
        return self._size

    def submit(self, func, *args, **kwargs) -> Future:
        """
        Submit a task to the process pool.
        Pickling is handled by ProcessPoolExecutor automatically.
        """
        # Note: We don't need manual pickle wrapper here usually, 
        # but to match InterpreterPool behavior (which wraps args), 
        # we can just submit directly if the func is picklable.
        return self._executor.submit(func, *args, **kwargs)

    def shutdown(self):
        self._executor.shutdown(wait=True)

def _unpickle_runner(payload_bytes):
    """
    Helper to unpickle and run.
    """
    import pickle
    func, args, kwargs = pickle.loads(payload_bytes)
    return func(*args, **kwargs)

def shared_test_task(x, y=0):
    """
    Helper function for testing. 
    Must be here to be reliably shareable/importable by sub-interpreters.
    """
    return {"sum": x + y, "context": "sub"}

def parallel_cpu_task(x):
    import os
    import threading
    return {
        "x_squared": x * x,
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "context": "sub"
    }

def slow_cpu_task(duration):
    import time
    time.sleep(duration)
    return "done"
