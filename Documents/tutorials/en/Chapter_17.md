# Chapter 17: Sync & Async Coordination - Theus Dispatcher

> **Target Audience:** Advanced Developers needing high-performance I/O integration.

Theus v3.0 introduces a revolutionary "Zero-Friction" dispatch system that allows you to mix Synchronous (CPU-bound) and Asynchronous (I/O-bound) code within the same workflow transparently.

## 1. The Challenge of Mixed Workloads

In traditional Python updates:
- **Sync Code** blocks the `asyncio` Event Loop (killing performance).
- **Async Code** requires complex `await` chains and cannot be easily called from Sync code.

Theus solves this by implementing an **Intelligent Dispatcher** inside the Rust Core (`engine.rs`).

## 2. Automatic Dispatch Mechanism

When you register a process via `@process`, Theus inspects the function signature at runtime using `inspect.iscoroutinefunction`.

### A. Async Functions (`async def`)
**Behavior:** Theus executes these **directly** on the main Event Loop.
**Use Case:** Network calls, Database queries, sleeping.
**Under the Hood:**
```python
# Theus Logic (Simplified)
result = await process(ctx) 
```

### B. Sync Functions (`def`)
**Behavior:** Theus **automatically wraps** these in a Thread Pool using `asyncio.to_thread` (Python 3.9+).
**Use Case:** Heavy calculations, Legacy libraries, CPU-bound logic.
**Under the Hood:**
```python
# Theus Logic (Simplified)
result = await asyncio.to_thread(process, ctx)
```
> **Benefit:** Your synchronous code **never blocks** the workflow engine. You don't need to manually verify thread safety or spawn threads.

## 3. Example: Hybrid Workflow

```python
import asyncio
import time
from theus.contracts import process

# 1. Async Process (Non-blocking I/O)
@process(outputs=['domain.data'])
async def fetch_data(ctx):
    # Runs on Event Loop
    print("Fetching...")
    await asyncio.sleep(1.0) # Does not block
    return "Data"

# 2. Sync Process (Blocking CPU)
@process(inputs=['domain.data'], outputs=['domain.result'])
def heavy_computation(ctx):
    # Runs in Thread Pool (Theus handles this!)
    print("Calculating...")
    time.sleep(2.0) # Blocks THREAD, not LOOP
    return "Result"

# 3. Spawning Background Tasks
@process(side_effects=['background_job'])
async def spawn_job(ctx):
    # Standard asyncio pattern works perfectly
    asyncio.create_task(heavy_background_job())
    return None
```

## 4. Integration with Tokio (Rust)

While Theus runs Python code on `asyncio` for compatibility, the textbf{Rust Core} uses **Tokio** for its internal systems (Audit Logging, SignalHub, File Writes).
- This "Twin-Turbo" architecture means your Python logic is flexible, while framework overhead is handled by Rust's ultra-fast executor.

---
**Summary:**
- Write `async def` for I/O.
- Write `def` for CPU.
- Theus handles the rest. No configuration needed.
