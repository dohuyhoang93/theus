# DR-003: Managed Shared Memory (Theus Allocator)

## 1. Context & Problem
Currently (v3.0.2), developers using Theus for Parallel Processing must manually manage `multiprocessing.shared_memory.SharedMemory` objects.
This leads to:
1.  **Boilerplate:** 10+ lines of setup/teardown code in `main.py`.
2.  **Safety Risks:** Forgetting `unlink()` causes RAM leaks (Zombie Memory).
3.  **Race Conditions:** Naming collisions if multiple instances run simultaneously.
4.  **UX Friction:** Partitioning logic (slicing) is manual manual.

## 2. Proposed Solution
Implement a **Managed Memory Allocator** within the `TheusEngine`. The Engine becomes the **Owner** of all shared memory segments, handling lifecycle, naming, and cleanup automatically.

### 2.1. The New API (Happy Path)

```python
# Create data directly via Engine
# Theus auto-generates a unique name: "theus:{session_uuid}:source_data"
# Theus auto-calculates size bytes.
arr_in = engine.heavy.alloc("source_data", shape=(20_000_000,), dtype=np.float32)

# Usage
arr_in[:] = np.random.rand(...)

# No explicit cleanup required. 
# Engine shutdown triggers auto-unlink.
```

## 3. Detailed Design

### 3.1. Namespace Isolation (Solving Conflicts)
Every memory segment created by Theus will follow a strict naming convention:
`theus:{session_uuid}:{pid}:{key}`
*   **session_uuid:** Unique ID generated at `TheusEngine.__init__`.
*   **pid:** Process ID of the creator (Owner).
*   **key:** User-friendly name (e.g., "input_image").

**Benefit:** Multiple Theus instances can run on the same machine without colliding, even if they use the same variable names.

### 3.2. Ownership Model (Solving Inter-Process Safety)
*   **Owner (Main Process):** Verification of `TheusEngine` instance.
    *   Responsive for `SharedMemory.unlink()` (Delete file).
*   **Borrower (Worker Process):**
    *   Theus passes the **Name** and **Shape** to the worker via `ParallelContext`.
    *   Worker maps the memory (`SharedMemory(name=...)`).
    *   Worker is **Restricted** to only `close()` (Process-level detach), strictly forbidden from calling `unlink()`.

### 3.3. Zombie Collector (Solving Edge Cases)
To handle crashes (SIGKILL) where `finally` blocks don't run:
1.  **Startup Scan:** When `TheusEngine` starts, it spawns a background thread (or checks synchronously) to scan system Shared Memory (e.g., `/dev/shm` or `Global\` namespace on Windows).
2.  **Liveness Check:** It parses names `theus:{uuid}:{pid}:{key}`.
3.  **Heuristic:** If process `{pid}` is NOT running:
    *   Assume safe to delete.
    *   Perform `unlink()` to reclaim RAM.

### 3.4. Rust Integration (Under the Hood)
We will introduce a `MemoryRegistry` in the Rust Core (`theus_core`):
*   Tracks all allocated segments.
*   Implements `Drop` trait to ensure `unlink` is called even if Python GC is messy.
*   Provides `get_stats()` for monitoring usage.

## 4. Implementation Plan (v3.1)

1.  **Python Layer:**
    *   Add `HeavyZoneManager` class in `theus/context.py`.
    *   Implement `alloc()` method wrapping `SharedMemory`.
    *   Implement `__del__` for safety cleanup.

2.  **Rust Layer (Optional but recommended):**
    *   Move registry to Rust for robustness against Python runtime crashes.

3.  **Process Context:**
    *   Update `HeavyZoneWrapper` to handle implicit strict mapping logic.

## 5. Alternatives Considered (Fair-mindedness)
Why build `Theus Allocator` instead of using Ray/Redis?

| Feature | Theus Native Allocator | Ray / Redis |
| :--- | :--- | :--- |
| **Philosophy** | **Microkernel** (Zero-Dependency) | **Monolith** (Heavy Infrastructure) |
| **Latency** | **~0ms** (Direct mmap) | **Low** (IPC/Socket overhead) |
| **Complexity** | Low (Just Python/Rust code) | High (Requires separate service/cluster) |
| **Control** | Granular (Per-tensor ownership) | Opaque (Store manages eviction) |

**Decision:** We choose Native Allocator to maintain Theus's "Library-first" nature. Users shouldn't need to spin up a Docker container just to share a matrix.

## 6. Consequences
*   **Positive:** "Zero-Boilerplate" parallel code. Higher system stability.
*   **Negative:** Implicit magic hides complexity. Users might assume memory is infinite. (Need Quotas).
*   **Risk:** PID Reuse. **Mitigation:** Zombie Collector must verify `Session UUID` in the SHM name matches an active session (or absence thereof) before deletion.

## 7. Verification Scenarios (Updated parallel_demo)
To validate this design, the `parallel_demo` must be updated to include:

### Scenario A: Zero-Boilerplate Integrity
*   **Goal:** Prove `alloc()` replaces 15 lines of cleanup code.
*   **Check:** Remove all `try...finally { shm.unlink() }` blocks. Run demo repeatedly.
*   **Success:** No memory leak warning in OS (e.g., check `/dev/shm`).

### Scenario B: The "Bad Worker" Trap
*   **Goal:** Prove isolation.
*   **Test:** Create a task `saboteur_task` that attempts to call `ctx.heavy['data'].shm.unlink()`.
*   **Success:** Theus wrapper intercepts/blocks the call OR the underlying OS handle is opened in a way (on Linux) that prevents unlinking from non-owner.

### Scenario C: Namespace Stress
*   **Goal:** Prove collision resistance.
*   **Test:** Spawn 2 independent instances of `main.py` simultaneously (Total 8 workers).
*   **Success:** Both finish with correct calculations. No `FileExistsError`.

### Scenario D: Crash Recovery (Zombie Test)
*   **Goal:** Prove self-healing.
*   **Test:** Run demo with `--crash` flag (sys.exit(9) mid-process). Then run normally.
*   **Success:** The second run detects the abandoned segments from Run 1 and cleans them before allocating new ones.
