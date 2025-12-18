import threading
import time
import queue
import pytest
from theus.orchestrator.executor import ThreadExecutor
from theus.orchestrator.bus import SignalBus
from theus.locks import LockManager, LockViolationError

def test_executor_basics():
    """Verify ThreadPool executes tasks and returns results."""
    exec_ = ThreadExecutor(max_workers=2)
    def task(x):
        return x * 2
    
    f = exec_.submit(task, 10)
    assert f.result(timeout=1) == 20
    exec_.shutdown()

def test_signal_bus():
    """Verify Thread-Safe Queue wrapper."""
    bus = SignalBus()
    bus.emit("Hello")
    assert bus.get() == "Hello"
    assert bus.empty()

def test_lock_manager_exclusion():
    """
    Verify that lock_mgr.unlock() provides MUTUAL EXCLUSION.
    If multiple threads try to 'unlock' (enter Write Mode) simultaneously,
    they must be serialized.
    """
    lock_mgr = LockManager(strict_mode=True)
    shared_resource = {"count": 0}
    
    def worker():
        # Attempt to enter "Write Mode"
        # This calls 'with self._mutex' inside
        with lock_mgr.unlock():
            # Critical Section
            # Simulate verify check
            lock_mgr.validate_write("count", shared_resource)
            
            # Read-Modify-Write
            curr = shared_resource["count"]
            time.sleep(0.001) # Force scheduler switch
            shared_resource["count"] = curr + 1

    # Run 50 concurrent writes
    threads = []
    for _ in range(50):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert shared_resource["count"] == 50, f"Race condition! Count is {shared_resource['count']}"

def test_lock_manager_violation_in_threads():
    """
    Verify that a thread CANNOT write if it hasn't called unlock().
    """
    lock_mgr = LockManager(strict_mode=True)
    ctx = {}
    
    def rogue_worker():
        try:
            lock_mgr.validate_write("foo", ctx)
        except LockViolationError:
            return "CAUGHT"
        return "MISSED"
        
    t = threading.Thread(target=rogue_worker) # Raw thread, no executor logic
    # We can't easily get return from Thread without queue, using executor for convenience
    exec_ = ThreadExecutor(max_workers=1)
    f = exec_.submit(rogue_worker)
    result = f.result()
    exec_.shutdown()
    
    assert result == "CAUGHT"
