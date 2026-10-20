# Theus v3.0.2 Release Notes

**Date:** 2026-01-26
**Status:** Production Ready (Audited)

## 🛡️ Security & Integrity (CRITICAL)

### Context Guard & Shadow Copy (CVE-Internal-2026-01 Fixed)
This release addresses a critical integrity vulnerability where legacy context accessors (`ctx.domain_ctx`) could leak raw Rust references, allowing unsafe state mutation.
- **Shadow Copy Enforcement:** The `ContextGuard` now enforces Copy-On-Write (Shadow Copy) semantics for all object mutations. 
- **Supervisor Proxy:** All legacy aliases are now wrapped in `SupervisorProxy` to ensure strict transaction isolation.
- **Safe Side-Effects:** Direct mutation of context objects (e.g., `ctx.domain.x = 1`) is now safe but **transient** (changes are discarded unless explicitly returned via `StateUpdate` or Dict, enforcing Functional Purity).

### Comprehensive Audit
The codebase has undergone and PASSED a full "Deep Dive" Security & Code Audit (Report: `Documents/AUDIT_V3_0_2.md`).
- **Integrity Verified:** No reference leaks.
- **Contract Enforcement:** Verified via Proof-of-Concept.
- **Zero Warnings:** 100% clean check from `cargo clippy` (Rust) and `ruff` (Python).

## Key Advancements

### Thread Safety & Concurrency Control
This release introduces a robust Conflict Manager implemented in Rust to handle high-concurrency scenarios safely:

- **Smart CAS (Key-Level Versioning):** Theus v3.0.2 upgrades from Strict CAS to **Smart CAS**. It now detects conflicts at the *Field Level*. If two processes update different keys (e.g., `domain.counter` vs `domain.user_list`), they can commit simultaneously without Version Conflict, significantly boosting throughput.
- **Exponential Backoff with Jitter:** The system now intelligently manages retry intervals when conflicts occur. Instead of fixed waiting, processes wait for strictly increasing durations (multiplied by 2 on each failure) with added randomized "jitter".
- **VIP Locking (Anti-Starvation):** To ensure fairness, the system employs a priority mechanism. If a process fails to commit its transaction 5 times, it is granted a "VIP Ticket", temporarily blocking other writers to guarantee progress.

### True Parallelism
- **Multi-Process Execution:** Enabled robust support for `ProcessPool`, allowing CPU-bound tasks to bypass the Python GIL explicitly.
- **Safety Integration:** The parallel execution engine is deeply integrated with the new Concurrency Control features to ensure data consistency across process boundaries.

### Shared Memory (Heavy Context)
Optimized the Heavy Zone for efficient data handling:
- **Zero-Copy Architecture:** Leverages shared memory to pass large datasets (Tensors, DataFrames) between processes without serialization overhead.
- **Hybrid Management:** The system intelligently handles cross-platform differences in shared memory naming (Windows/Linux) to ensure data integrity and accessibility.

## Improvements
- **Core Parity:** Achieved 100% logic alignment between the Rust Core engine and Python interface.
- **Stability:** Fixed configuration templates and import paths for parallel execution examples.
- **Standardization:** Codebase enforces strict architectural rules, vetted by both `cargo clippy` (Rust) and `ruff` (Python).

### 🐛 Critical Fixes
- **Flux Signal Blindness:** Fixed a race condition where ephemeral signals emitted by async processes were missed by the Flux Workflow engine. Signals are now properly latched in `State.last_signals` for one tick.
- **Numpy Compatibility:** `ContextGuard` now natively supports Numpy scalar types (`int64`, `float32`, etc.), preventing `TypeError` during mathematical operations.



## Known Limitations
- **Sub-Interpreter Compatibility:** While Theus supports PEP-554 (Sub-interpreters), major C-extensions like `numpy` do not yet support multi-phase initialization (`numpy._core._multiarray_umath` error). Therefore, the system currently defaults to `ProcessPool` for robust execution.
- **Zombie Collector (Windows):** Automatic cleanup of shared memory from crashed processes is currently experimental on Windows due to OS-specific naming constraints (fully functional on Linux).

## Installation
```bash
pip install theus==3.0.2
```
