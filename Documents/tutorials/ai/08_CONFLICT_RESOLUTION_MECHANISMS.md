# 08_CONFLICT_RESOLUTION_MECHANISMS.md

**Status:** Active (3.0.2)
**Component:** `theus_core` (Rust)

## Overview
This document specifies the internal workings of the Advanced Conflict Resolution system deployed in Theus v3.0.2. It is designed to handle High Contention scenarios (Thundering Herd) and prevent Starvation (Livelock).

## Architecture

The conflict logic is implemented in Rust within `theus_core` to ensure thread safety and strict atomicity.

### 1. Data Structures

#### `State` (`structures.rs`)
The Immutable State structure has been augmented with Key-Level Versioning.
```rust
struct State {
    ...
    version: u64, // Global Version
    key_last_modified: HashMap<String, u64>, // Last Version specific key was touched
}
```

#### `ConflictManager` (`conflict.rs`)
Manages retry policies and priority.
```rust
struct ConflictManager {
    failures: HashMap<String, u32>, // Failure count per process
    vip_holder: Mutex<Option<String>>, // Current VIP Process (Priority Lock)
    ...
}
```

## Algorithms

### 1. Compare-And-Swap (Smart CAS)
**Flow:**
1.  **Check VIP:** Is `vip_holder` active?
    -   If YES and `requester != vip_holder`: Return `SystemBusy` (Block).
    -   If YES and `requester == vip_holder`: Proceed.
    -   If NO: Proceed.
2.  **Global Check:** `current.version == expected.version`?
    -   Yes: UPDATE -> Commit.
    -   No: Proceed to Smart Check.
3.  **Smart Check (Field-Level v3.1):** For each modified field `F` in Update:
    -   Lookup: `last_modified = key_last_modified[F]`.
    -   Tracked Path: e.g., `domain.counter` (exact path), not just `domain`.
    -   Rule: Is `last_modified <= expected.version`?
    -   **Result:**
        -   If ALL modified fields are safe: UPDATE -> Commit (Partial Merge).
        -   If ANY modified field has changed since `expected.version`: Return `ContextError` (CAS Mismatch).

### 2. Exponential Backoff
**Policy:**
-   **Base Delay:** 2ms.
-   **Formula:** `delay = base * 2^(retries - 1)`.
-   **Jitter:** `delay = delay * random(0.8, 1.2)`.
-   **Max Retries:** 5.

### 3. Priority Escalation (Starvation Rescue)
**Logic:**
-   If `retries >= 5`:
    -   Acquire `vip_holder` lock.
    -   Engine blocks all other writes (`is_blocked() -> True`).
    -   VIP Process retries immediately.
    -   Upon Success: `vip_holder` is released.

## Error Handling

### 1. `ContextError` ("CAS Version Mismatch")
-   **Meaning:** Genuine data conflict.
-   **Action:**
    -   Call `engine.report_conflict()`.
    -   Sleep for `decision.wait_ms`.
    -   Retry loop.

### 2. `ContextError` ("System Busy")
-   **Meaning:** System is Locked by VIP.
-   **Action:**
    -   Sleep for fixed interval (e.g., 50ms).
    -   Retry loop.

## Invariants
1.  **Serializability:** Use of `key_last_modified` guarantees that no update overwrites unseen data.
2.  **Liveness:** Backoff prevents Thundering Herd; Priority Ticket prevents Starvation.
3.  **Fairness:** Eventually, every attempting process will either succeed or trigger VIP to force success.

## Fork Safety (Multiprocessing)

### Naming Convention
Shared Memory segments follow the pattern:
```
theus:{session_id}:{pid}:{user_key}
```
- `session_id`: Random UUID prefix (per Engine instance).
- `pid`: **Dynamic** - Captured via `os.getpid()` at allocation time.
- `user_key`: User-provided key.

### Ownership Tracking
`HeavyZoneAllocator` stores `(shm, arr, creator_pid)` for each allocation.
- **Cleanup Rule:** `if os.getpid() == creator_pid: shm.unlink()`.
- **Implication:** Forked children will NOT unlink parent's segments.

### Worker Constraints
Workers (`@process(parallel=True)`) receive `HeavyZoneWrapper` (read-only), NOT `HeavyZoneAllocator`.
- **Allowed:** `ctx.heavy[key]` (Read).
- **Forbidden:** `ctx.heavy.alloc(...)` (Raises `AttributeError`).

### Zombie Reaper
`MemoryRegistry.scan_zombies()` runs on startup:
1. Reads `.theus_memory_registry.jsonl`.
2. Checks PID liveness via `sysinfo`.
3. Unlinks segments owned by dead processes.

