from theus.contracts import process
from theus.structures import StateUpdate
import os

# 1. Define a Parallel Task that Returns a Result
@process(outputs=["evidence"], parallel=True)
def heavy_worker_task(ctx):
    pid = os.getpid()
    return StateUpdate(key="evidence", val=f"Processed by PID {pid}")

# 2. Define a Parallel Task that FAILS
@process(parallel=True)
def failing_worker_task(ctx):
    raise ValueError("Sabotage from Worker!")
