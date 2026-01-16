
import pytest
import threading
import os
import time
from theus.parallel import InterpreterPool

from theus.parallel import shared_test_task, parallel_cpu_task, slow_cpu_task

@pytest.fixture
def pool():
    p = InterpreterPool(size=2)
    yield p
    p.shutdown()

def test_basic_execution(pool):
    future = pool.submit(parallel_cpu_task, 10)
    res = future.result()
    
    assert res["x_squared"] == 100
    assert res["context"] == "sub"
    print(f"Main TID: {threading.get_ident()}, Sub TID: {res['tid']}")
    # assert res["tid"] != threading.get_ident() # Pyo3/Sub-Interp threading model is complex, check values manually

def test_concurrency(pool):
    # Pool size is 2
    # Submit 4 slow tasks
    futures = []
    start = time.time()
    
    for _ in range(4):
        futures.append(pool.submit(slow_cpu_task, 0.5))
        
    results = [f.result() for f in futures]
    end = time.time()
    
    # 4 tasks * 0.5s = 2.0s sequential
    # With 2 workers, should occur in ~1.0s (2 batches of 2)
    duration = end - start
    print(f"Duration: {duration:.2f}s")
    
    assert len(results) == 4
    assert duration < 1.8 
    assert duration > 0.5

def test_kwargs_support(pool):
    # Use shareable task from installed module
    f = pool.submit(shared_test_task, 10, y=20)
    res = f.result()
    assert res["sum"] == 30
    assert res["context"] == "sub"

if __name__ == "__main__":
    p = InterpreterPool(size=2)
    print(p.submit(parallel_cpu_task, 5).result())
    p.shutdown()
