# Chapter 19: Zero-Copy Parallelism in Theus V3

## Overview
Theus V3 introduces a **Hybrid Zero-Copy Parallelism** model designed for high-performance AI workloads. Unlike standard Python multiprocessing which relies on expensive Pickle serialization, Theus leverages a **Smart Pickling** strategy combined with **Managed Shared Memory** to pass massive datasets between processes instantly.

**Key Benefits:**
- **>2x Speedup** for heavy data workloads (>100MB).
- **True Parallelism:** Bypasses GIL using Process Pools.
- **Safety:** Automatic Lifecycle Management (No Zombie Segments).

## Core Concepts

### 1. `ctx.heavy` (The Zero-Copy Zone)
The `heavy` zone in the context is no longer a standard dictionary. It is a strictly controlled **Shared Memory View**.
- **Write:** When you use `alloc()`, Theus creates a named memory segment managed by the Rust Core.
- **Read:** When a worker accesses `ctx.heavy`, it receives a **Read-Only** view of the data without copying bytes.

### 2. `@process(parallel=True)`
This decorator marks a function for execution in the Parallel Pool.
- **Auto-Dispatch:** `engine.execute()` automatically detects this flag and routes execution to a worker.
- **Context Isolation:** The worker receives a stripped-down `ParallelContext` containing:
    - `ctx.domain` (Copy of input args + domain state)
    - `ctx.heavy` (Zero-Copy handle)
    
## Usage Guide

### Step 1: Define a Parallel Task
Create a function decorated with `@process(parallel=True)`.

```python
import numpy as np
from theus.contracts import process

@process(parallel=True)
def heavy_compute(ctx):
    # 1. Access Data (Zero Cost)
    # ctx.heavy['matrix'] is a ShmArray (numpy subclass)
    # This maps the existing memory segment instantly.
    data = ctx.heavy['matrix'] 
    
    # 2. Compute (Releases GIL if using Numpy)
    result = np.linalg.det(data)
    
    # 3. Return lightweight metadata results
    return {"det": result}
```

### Step 2: Orchestration (Main Process)
Initialize the engine and allocate Managed Memory.

```python
from theus import TheusEngine
import numpy as np

# 1. Initialize Engine
engine = TheusEngine()

# 2. Alloc Managed Memory (v3.2 API)
# No manual SharedMemory setup! No unlink logic!
arr = engine.heavy.alloc("matrix", shape=(5000, 5000), dtype=np.float32)

# 3. Populate Data
arr[:] = np.random.rand(5000, 5000)

# 4. Inject into Context
engine.compare_and_swap(engine.state.version, heavy={'matrix': arr})

# 5. Execute (Auto-Dispatched to Worker)
# The worker receives the 'matrix' handle, not the payload.
result = await engine.execute(heavy_compute)
print(f"Determinant: {result['det']}")
```

## Best Practices
1.  **Don't Pickle Big Data:** Never pass large arrays via `input_args`. Put them in `ctx.heavy`.
2.  **Return Small Metadata:** Workers should return aggregation results (scores, bounding boxes), not large arrays.
3.  **Use `alloc()`:** Always use `engine.heavy.alloc()` instead of `multiprocessing.shared_memory`. It ensures:
    *   **Collision Safety:** Unique names per session/PID.
    *   **Cleanup Safety:** Deletes memory if your script crashes (Zombie Recovery).

## Troubleshooting

### `AttributeError: 'ProcessContext' object has no attribute 'input'`
- **Cause:** You are trying to access inputs that were merged into `ctx.domain`.
- **Fix:** Use `ctx.domain` or the alias `ctx.input` (available in v3.0.2+).

### `BrokenProcessPool` / `PicklingError`
- **Cause:** You are passing non-picklable objects (like threading locks or open files) in `ctx.domain`.
- **Fix:** Ensure all domain/input data is simple JSON-serializable types.
