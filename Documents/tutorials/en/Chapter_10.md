# Chapter 10: Performance Optimization & Managed Memory

In modern AI applications, especially Reinforcement Learning and Computer Vision, moving data is often more expensive than computing on it. Theus v3.2 introduces valid solution for this: **Managed Shared Memory** and **Zero-Copy Parallelism**.

This chapter guides you through optimizing Theus for high-load scenarios, allowing you to process Gigabit-sized tensors in milliseconds.

## 1. The Heavy Data Problem
When you pass a large Numpy array (e.g., a 1080p frame buffer or a 1GB Experience Replay) between Python processes, standard libraries (`multiprocessing`) use **Pickle**.
1.  **Serialize:** The sender copies data into bytes.
2.  **Transfer:** Bytes are sent over a pipe.
3.  **Deserialize:** The receiver allocates new memory and copies bytes back.

**Result:** A 1GB transfer freezes the main process for seconds and doubles RAM usage.

## 2. The Solution: Managed Shared Memory
Theus v3.2 solves this with a **Hybrid Architecture**:
*   **Rust Allocator:** Allocates memory directly from the OS (`mmap` on `/dev/shm` or Windows Pagefile).
*   **Zero-Copy Access:** Python processes receive a lightweight "pointer" (Descriptor), not the data itself.
*   **Lifecycle Engine:** Theus automatically tracks every allocation and cleans it up, even if processes crash.

### 2.1 The API: `HeavyZoneAllocator`
Instead of creating Numpy arrays directly, use **HeavyZoneAllocator** to allocate them in managed shared memory.

```python
from theus.context import HeavyZoneAllocator
import numpy as np

# Create allocator (auto-scans for zombies on init)
allocator = HeavyZoneAllocator()

# Create a 20 Million Element Float Array (approx 80MB)
# Returns a 'ShmArray' which behaves exactly like a Numpy Array
arr = allocator.alloc("camera_feed", shape=(20_000_000,), dtype=np.float32)

# Use it normally
arr[:] = np.random.rand(20_000_000)
print(arr.mean())
```

**What happens under the hood?**
1.  **Rust Registry:** Theus Core creates a named shared memory segment (e.g., `theus:uuid:pid:camera_feed`).
2.  **Journaling:** The allocation is logged to `.theus_memory_registry.jsonl` for safety.
3.  **Mapping:** The Python object maps this file directly to RAM.

### 2.2 Parallel Consumer (Zero-Copy)
When you pass a ShmArray to a worker (via pickle or `@process(parallel=True)`), it transfers by reference.

```python
from theus.context import HeavyZoneAllocator
from theus import TheusEngine, process
import numpy as np

# Main Process: Allocate shared memory
allocator = HeavyZoneAllocator()
arr = allocator.alloc("input_data", shape=(1000, 1000), dtype=np.float32)
arr[:] = np.random.rand(1000, 1000)

# Inject into Engine state via direct CAS
engine = TheusEngine(context={...})
engine._core.compare_and_swap(engine.state.version, None, {'input_data': arr}, None)

# Worker Process
@process(parallel=True)
def process_data(ctx):
    # This does NOT copy 4MB
    # Worker reconstructs ShmArray from shared memory name (microseconds)
    data = ctx.heavy['input_data']
    
    # Fast calculation on shared memory
    return np.sum(data)

engine.register(process_data)
result = await engine.execute(process_data)
```

## 3. Safety: The Rust "Iron Gauntlet"
Working with Shared Memory manually (`multiprocessing.shared_memory`) is dangerous because of **Zombie Segments**. If a script crashes before calling `unlink()`, that RAM is lost until reboot.

Theus Core (Rust) handles this automatically:
1.  **Registry File:** Every allocation is persisted on disk.
2.  **Zombie Collector:** On every startup, Theus scans the registry.
3.  **Liveness Check:** If it spots a segment owned by a dead process (PID check via `sysinfo`), it **automatically unlinks it**.

> **Note:** You never need to call `unlink()`. Theus owns the memory.

## 4. Strict Guards Optimization
For training loops where milliseconds count, you can disable the Transactional Safety Layer completely.

```python
# Maximum Speed Mode
engine = TheusEngine(strict_guards=False, strict_cas=False)
```

| Defense Layer | **Strict Guards = True** (Default) | **Strict Guards = False** (Training) | **Managed Memory** (New) |
| :--- | :--- | :--- | :--- |
| **1. Transaction (Rollback)** | ✅ **Enabled** | ❌ **Disabled** | N/A |
| **2. Audit Policy** | ✅ **Active** | ⚠️ **Optional** | ✅ **Active** |
| **3. Memory Access** | Copy-on-Write (Safe) | Direct access | **Zero-Copy (Shared)** |
| **4. Performance Impact** | Medium (Safety cost) | Low | **Near Zero** |

## 5. Best Practices
1.  **Use `HeavyZoneAllocator` for Big Data:** Anything > 1MB (Images, Audio, Replay Buffers).
2.  **Use Standard Dicts for Metadata:** Configs, labels, IDs should stay in `ctx.data` (Context).
3.  **Don't Re-allocate in Loops:** Allocate buffers once at startup, then overwrite contents (`arr[:] = new_data`) to save allocation overhead.
4.  **Batch Processing:** When using Parallel Processes, chunk data logically (e.g. by index) rather than slicing the array if possible, though slicing `ShmArray` works correctly (returns a view).
5.  **Cleanup:** Call `allocator.cleanup()` when done, or rely on `atexit` handler (automatic on normal exit).

**Example cleanup:**
```python
allocator = HeavyZoneAllocator()
try:
    arr = allocator.alloc("data", shape=(1000000,), dtype=np.float32)
    # ... use arr ...
finally:
    allocator.cleanup()  # Ensures unlink even on exception
```

## 6. Architecture Summary
Theus v3.2 transforms the Memory Management landscape:
*   **Python:** Provides the flexible Interface (Numpy compatibility).
*   **Rust:** Provides the robust Enforcer (Registry, Cleanup).
*   **Result:** You get the ease of Python with the memory safety of a C++ engine.
