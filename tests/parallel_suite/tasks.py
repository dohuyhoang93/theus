import time
import os
import sys

# Try importing StateUpdate. 
# In the sub-interpreter (with the fix), this should work as a Pure Python class
# even if theus_core fails to load.
from theus.structures import StateUpdate

from theus.contracts import process

@process(inputs=["item"], outputs=["last_echo"], parallel=True)
def task_standard_echo(ctx):
    """
    Case Mẫu: Standard Echo.
    Verifies basic input/output and StateUpdate creation.
    """
    item = ctx.input.get("item", "nothing")
    return StateUpdate(key="last_echo", val=f"Echo: {item}")

@process(inputs=["n"], outputs=["compute_result"], parallel=True)
def task_heavy_compute(ctx):
    """
    Case Liên Quan: CPU Bound.
    Verifies execution isolation and performance.
    """
    n = ctx.input.get("n", 1000)
    # Simple CPU waster
    result = sum(i * i for i in range(n))
    return StateUpdate(key="compute_result", val=result)

@process(inputs=["size_mb"], outputs=["heavy_payload"], parallel=True)
def task_large_payload(ctx):
    """
    Case Biên: Large Payload.
    Verifies serialization mechanism resilience.
    """
    size_mb = ctx.input.get("size_mb", 1)
    # Generate large string
    data = "X" * (size_mb * 1024 * 1024)
    return StateUpdate(key="heavy_payload", val=len(data)) # Don't return the data itself to avoid IPC choke, just verify we processed it.

@process(inputs=["target_version", "val"], outputs=["race_key"], parallel=True)
def task_conflict_generator(ctx):
    """
    Case Mẫu Thuẫn: Conflict Generator.
    Designed to return a fixed key/version to intentionally cause CAS race in main process.
    """
    target_version = ctx.input.get("target_version", 1)
    # Everyone tries to set 'race_key' to their ID
    worker_id = str(os.getpid()) # Or some random ID
    import uuid
    val = ctx.input.get("val", str(uuid.uuid4()))
    
    return StateUpdate(
        key="race_key", 
        val=val,
        assert_version=target_version
    )

@process(parallel=True)
def task_crash_test(ctx):
    """
    Case Biên: Error Handling.
    """
    raise ValueError("Intentional Crash in Sub-interpreter")
