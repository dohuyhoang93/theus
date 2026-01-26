# Zero-Copy Coding Guidelines for AI Agents

**Target Audience:** AI Code Generators (Agentic Systems)
**Framework Version:** Theus v3.2+

## 1. Golden Rules
When generating code for Theus V3.2, you MUST adhere to these rules to prevent system crashes and performance degradation.

### Rule #1: parallel=True requires Statelessness
- **Do:** Use `@process(parallel=True)` for CPU/GPU intensive tasks.
- **Don't:** Access global variables, locks, or database connections inside a parallel process.
- **Reason:** Parallel processes run in isolated memory spaces (Process Pool).

### Rule #2: Heavy Data MUST be Zero-Copy
- **Do:** Read large arrays from `ctx.heavy`.
- **Don't:** Pass large arrays into `inputs=[...]` or `input_args`.
- **Constraint:** `ctx.heavy` is Read-Only in the worker. Do not attempt to mutate it in-place.

### Rule #3: Managed Allocation
- **Do:** Use `engine.heavy.alloc("key_name", shape=...)` to create shared arrays.
- **Don't:** Manually instantiate `multiprocessing.shared_memory.SharedMemory`.
- **Reason:** `alloc()` registers the memory with the Rust Core (`theus_core`), enabling Automatic Cleanup (Zombie Protection) and collision monitoring.

## 2. Code Generation Templates

### Template A: The Parallel Worker
Use this structure when the user asks for "High Performance" or "Heavy Calculation".

```python
from theus.contracts import process
import numpy as np

# AI NOTE: inputs are merged into ctx.input (or ctx.domain)
@process(parallel=True)
def compute_heavy_task(ctx):
    # 1. READ (Zero-Copy)
    # Theus guarantees 'large_dataset' is available if configured
    data = ctx.heavy.get('large_dataset')
    if data is None:
        return {"error": "Dataset missing"}

    # 2. PROCESS (Numpy/Torch)
    # Use vectorized operations on the Shared Memory View
    result = np.sum(data)

    # 3. RETURN (Lightweight)
    return {"sum": float(result)}
```

### Template B: The Orchestrator
Use this when setting up the engine with heavy data.

```python
import os
# AI NOTE: Force Process Backend for Windows/Numpy compatibility
os.environ["THEUS_USE_PROCESSES"] = "1"

from theus import TheusEngine
import asyncio
import numpy as np

async def main():
    engine = TheusEngine(...)
    
    # AI NOTE: v3.2 Managed Memory Pattern
    # 1. Allocate Shared Memory (Rust Managed)
    arr = engine.heavy.alloc("large_dataset", shape=(1000, 1000), dtype=np.float32)
    
    # 2. Populate
    arr[:] = np.random.rand(1000, 1000)
    
    # 3. Inject (Zero-Copy)
    # Note: 'arr' is already a ShmArray, so it wraps itself correctly.
    engine.compare_and_swap(engine.state.version, heavy={'large_dataset': arr})
    
    # 4. Execute
    await engine.execute("compute_heavy_task")
```

## 3. Common Error Recovery

- **Error:** `AttributeError: input`
  - **Fix:** Change `ctx.input` to `ctx.domain`. (Fixed in v3.0.2+, but good fallback).
  
- **Error:** `BrokenProcessPool`
  - **Fix:** Check if you are passing `Lock`, `FileHandle`, or `DatabaseConnection` in the context. Remove them.

- **Error:** `PermissionError` during `unlink()`
  - **Fix:** Ensure you are NOT calling `.unlink()` manually. Theus Rust Core owns the memory. Remove any manual cleanup code.
