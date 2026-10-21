# Release Notes v3.0.27

**Release Date:** 2026-10-21  
**Author:** Do Huy Hoang ([@dohuyhoang93](https://github.com/dohuyhoang93))  
**Cycle:** Correctness & Transactional OCC Hardening  
**Resolved Incidents:** INC-027, INC-028, INC-029  
**Open Incidents:** INC-030 (Commit CoW O(N²) latency — not addressed in this release)  

---

## Overview

Version 3.0.27 is a critical **Transaction Correctness & Concurrency Safety** release. It closes three interconnected vulnerabilities in the transaction commit and Optimistic Concurrency Control (OCC) boundary. All known OCC bypass paths on tested code paths are eliminated; the correctness claim is scoped to: **"no known OCC bypass on verified paths."** (See Known Limitations below.)

---

## Breaking Changes & API Migration

### 1. `set_strict_cas` and `set_strict_guards` Method Delegation Removed

In earlier versions, `TheusEngine` loosely delegated unresolved attribute lookups to its underlying Rust core `_core` via class-level `__getattr__`. Following the encapsulation hardening in INC-027, direct `__getattr__` delegation has been eliminated.

* **Impact:** Calling `engine.set_strict_cas(...)` or `engine.set_strict_guards(...)` directly now raises `AttributeError: 'TheusEngine' object has no attribute 'set_strict_cas'`.
* **Migration:** Use the standard Python property setters instead:
  ```python
  # Old (Deprecated / Removed):
  # engine.set_strict_cas(True)
  # engine.set_strict_guards(False)

  # New (Idiomatic):
  engine.strict_cas = True
  engine.strict_guards = False
  ```
  Both properties cleanly update Python-side flags and propagate the configuration to the underlying Rust core.

---

## Bug Fixes

### [INC-027] `commit_state` OCC Bypass & Unchecked Rust Export (High)
* **Problem:** `TheusEngine.commit_state` was exposed as a callable method without OCC version checks, allowing unverified state updates.
* **Fix:** Un-exported `commit_state` from `#[pymethods]`. `Transaction::__exit__` now performs direct Rust-internal state assignment at the point of durability.

### [INC-028] `Transaction.__exit__` OCC Gap (Medium)
* **Problem:** Context manager commits bypassed optimistic concurrency conflict detection present in `compare_and_swap`.
* **Fix:** Introduced key-level OCC conflict check inside `Transaction::__exit__`.

### [INC-029] Version 0 OCC Blindspot & Sentinel Ambiguity (High)
* **Problem:** `Transaction.start_version` was initialized to `0` as an "unopened" sentinel. However, a newly created `State` also starts at version `0`. The check `if self.start_version > 0` caused every transaction starting from the initial state to completely skip OCC validation, allowing concurrent initial transactions to silently overwrite each other without conflict detection.
* **Fix:**
  - Introduced explicit `TransactionLifecycle` FSM (`Unopened -> Active -> Committing -> Committed | Failed`, with `Active -> Aborted` on context exit exception).
  - Unified field conflict detection into shared Rust helper `detect_field_conflict(&current_state, start_ver, pending_data, pending_heavy)`.
  - The guard now runs for every transaction, including `start_version == 0`; a version difference triggers the field-level overlap check, and disjoint-field commits still succeed.
  - Restored strict fail-fast `?` downcast in signal structures to prevent silent drop of malformed signals.

---

## CI & Tooling Enhancements

### 1. Strict API Parity Gate with Explicit Allowlist
* `tests/verify_api_parity.py` now enforces 100% classification of all exported Rust core methods against Python wrapper capabilities:
  - Methods with property mappings (`strict_cas`, `strict_guards`) are strictly verified as `property` descriptors.
  - Rust-internal wiring and telemetry callbacks (`report_success`, `report_conflict`, `set_audit_system`, `execute_process_async`) are registered with explicit architectural justifications.
  - Any newly exposed Rust method that lacks wrapper coverage or an allowlist entry immediately triggers a hard test failure.

### 2. Unified CI Pipeline
* `python scripts/Local_CI.py full` now incorporates `step_verify_parity` alongside static analysis, unit tests, automated pytest suites, and manual verification scripts.

---

## Known Limitations

### [INC-030] Commit CoW O(N²) Sequential Write Latency — Open

`State::update()` performs a full clone of the durable document set on every commit. As the set
grows to N entries, a burst of N sequential writes costs O(N²) total clone work.

| N    | Measured elapsed (v3.0.27, isolated process) |
|------|----------------------------------------------|
| 100  | ~0.04s                                        |
| 500  | ~0.90s                                        |
| 1000 | ~7.5s (7.40s / 7.77s measured)               |

This is a structural issue pre-dating v3.0.27 (identical profile at v3.0.26 baseline). The
proposed fix is to replace `HashMap` with a persistent structural-sharing map (`im::HashMap`).
See [INC-030](../Incidents/by-area/core/INC-030_CommitCoW_Sequential_Write_Quadratic_Latency.md).

### Subinterpreter Race Condition Coverage — Incomplete

`theus_core` does not support loading in CPython subinterpreters (`does not support loading in
subinterpreters`). Tests that exercise multi-interpreter concurrency fall back to pure Python
mode, leaving subinterpreter-specific race conditions unverified.

The correct correctness claim for this release is therefore:
> **"No known OCC bypass on verified single-interpreter paths."**
> Multi-interpreter race conditions are not yet covered.
