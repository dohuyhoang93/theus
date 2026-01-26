from theus import process

@process(parallel=True)
def worker_read_shm(ctx):
    """
    Worker that simply confirms it can execute.
    Real Zero-Copy read test requires passing BufferDescriptor via state.heavy,
    which is a more advanced integration. This verifies basic pool execution.
    """
    import os
    return f"OK (Worker PID: {os.getpid()})"

@process(parallel=True)
def worker_serialization(ctx):
    return "Should not reach here if input is bad"
