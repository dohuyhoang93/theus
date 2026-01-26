# Chapter 20: Advanced Conflict Resolution (Smart CAS & Priority)

As you scale your Theus application to handle high concurrency (e.g., hundreds of parallel agents or intense sensor fusion), simple "Optimistic Locking" (Global CAS) can become a bottleneck. 

From **Theus v3.0.2**, the framework includes a sophisticated **Advanced Conflict Resolution** engine built directly into the Rust Core. This system automatically handles contention, prevents livelocks, and maximizes parallelism without requiring changes to your application code.

## 1. The Concurrency Challenge

In Theus, state is **Immutable**. Mutating state means creating a new "Version".
- **Old Behavior (v3.0.1):** If 10 workers try to update the State at version `100` simultaneously:
    - Worker 1 succeeds -> Version `101`.
    - Workers 2-10 fail (CAS Mismatch: Expected `100`, Found `101`).
    - **Result:** High failure rate, wasted CPU ("Thundering Herd").

## 2. Solution: Smart CAS (Key-Level Optimism)

Theus v3.0.2 introduces **Smart CAS (Compare-And-Swap)**. instead of checking the *Global Version*, the Engine now tracks the version of **Each Individual Key**.

### How it Works
When a transaction attempts to commit:
1.  **Global Check:** The Engine checks global version. If matched -> Commit (Fast Path).
2.  **Smart Check:** If global version mismatch, the Engine checks **only the keys you modified**.
    - If `key_A` (your target) has NOT changed since you started -> **Merge is Safe**.
    - If `key_A` HAS changed -> Confirm Conflict.

**Benefit:** Two workers can update *different keys* simultaneously without blocking each other, even if they started from the same version. This unlocks massive parallel throughput for disjoint workloads.

## 3. Automatic Adaptive Backoff

When genuine conflicts occur (e.g., 50 workers updating the *same* counter), Theus prevents the system from crashing via **Exponential Backoff**.

- **Mechanism:** If a CAS fails, the Engine waits briefly before retrying.
- **Algorithm:** `Wait = Base_Delay * 2^Retries + Jitter`
    - Retry 1: Wait ~2ms
    - Retry 2: Wait ~4ms
    - ...
    - Retry 5: Wait ~32ms
- **Result:** The "Thundering Herd" is serialized naturally. The load is spread out over time, allowing all transactions to eventually succeed.

## 4. Priority Ticket (Anti-Starvation)

To prevent "Fast" workers from always beating "Slow" workers (Starvation/Livelock), Theus implements a **Fairness Guarantee**:

- **Trigger:** If a worker fails 5 consecutive times.
- **Action:** The worker is granted a **VIP Ticket**.
- **Effect:** The Engine **LOCKS** the entire system against new writers for a short window. All other requests receive a "System Busy" signal and must wait.
- **Outcome:** The VIP worker gets exclusive access to commit its changes.

> [!NOTE]
> This mechanism essentially switches the system from **Parallel Mode** to **Serialized Mode** (Active Queue) temporarily to rescue struggling processes.

## 5. Developer Guide

You do not need to enable these features; they are active by default. However, you can optimize for them:

### Best Practice: Granular Outputs
Define strict `outputs` in your contracts.
```python
@process(outputs=["domain.camera_data"]) # Good: Only locks camera_data
def process_camera(ctx):
    ...
```
If you declare `outputs=["domain"]` (Root), Smart CAS assumes you might touch *anything*, reducing efficient merging.

### Best Practice: Handle "System Busy"
If you are writing manual retry loops (bypassing `engine.execute`), handle the `System Busy` error by sleeping.
```python
try:
    engine.compare_and_swap(...)
except ContextError as e:
    if "System Busy" in str(e):
        time.sleep(0.05) # Respect VIP
```
*Note: `engine.execute()` handles this automatically.*

## 6. Fork Safety (Multiprocessing)

When using `multiprocessing` or `ProcessPool`, Theus ensures memory isolation via **Dynamic PID Naming**.

### How it Works
- Shared Memory segments are named: `theus:{session}:{pid}:{key}`
- The `{pid}` is captured **at allocation time** (not process start), ensuring forked children get unique names.
- Each allocation tracks its `creator_pid`. Only the creator process can **unlink** (delete) the segment.

### Worker Constraints
> [!IMPORTANT]
> Worker processes (via `@process(parallel=True)`) can only **READ** shared memory allocated by the Main process. They **CANNOT** call `ctx.heavy.alloc()`.

This is by design: Main allocates, Workers consume (Zero-Copy Read). This prevents memory leaks from orphaned segments and ensures deterministic cleanup.

### Zombie Cleanup
If the Main process crashes (`kill -9`), orphaned segments are cleaned up automatically on the next Theus startup via the **Startup Check** (Zombie Reaper) in the Rust Core.

