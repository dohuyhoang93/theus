---
id: INC-002
title: PermissionError in ContextGuard (Pure Process Write Block)
area: interop
severity: high
introduced_in: v3.1.0
fixed_in: v3.1.1
status: resolved
---

# INC-002: PermissionError in ContextGuard

## Summary
Users encountered a `PermissionError: PURE process cannot write to 'domain.counter'` when attempting legal mutations inside an `@process` decorated function. This occurred because the `ContextGuard` failed to elevate the Read-Only SupervisorProxy to a Mutable Proxy, effectively blocking valid writes.

## Background
Theus v3.1 introduces a Supervisor/Worker architecture. By default, access to State is Read-Only. When entering a Process (Action), the system typically "elevates" specific context paths to be Mutable, wrapping them in a Transaction. This mechanism relies on `ContextGuard` receiving a valid `Transaction` object to link the proxy to the delta log.

## What Went Wrong
The `app_logic_process` function in `engine.py` created a `ContextGuard` but failed to pass the active `Transaction` object (`tx`) to it. As a result, `ContextGuard` fell back to its default "Safe Mode", which wraps the target in a Read-Only `SupervisorProxy`. When the user code tried to write (`+= 1`), the Proxy correctly (but inconveniently) enforced the read-only constraint.

## Impact
- **Affected:** All users of the `@process` decorator in v3.1.0 attempting to modify state.
- **Behavior:** `PermissionError` crash. Transaction aborted.
- **Severity:** High. It rendered the core feature of the framework (safe mutation) unusable.

## Root Cause
- **Logical Gap:** Integration logic in `engine.py` assumed `ContextGuard` could auto-discover the transaction or that Rust handled it entirely.
- **Inconsistent Contract:** The Python layer (UI) and Rust layer (Core) had a mismatch in expectations regarding who manages the Transaction lifecycle.

## Why This Was Hard to Detect
- **Implicit Dependency:** `ContextGuard` silently degraded to Read-Only mode instead of failing during initialization if `tx` was missing (Defensive Coding backfired).

## Resolution
- **Explicit Lifecycle:** Updated `engine.py` to explicitly initialize `theus_core.Transaction`.
- **Dependency Injection:** Passed the `tx` object into `ContextGuard` constructor.
- **Commit Logic:** Added explicit `compare_and_swap` with `tx.pending_data` at the end of the execution flow.

## Long-Term Changes
- **Strict Typing:** `ContextGuard` now validates strict requirements for `tx` if `mode="write"`.
- **Interop Pattern:** Established the pattern that "Python manages Lifecycle/Glue, Rust manages State/Storage".

## Related
- **Post-Mortem:** Documents/Incidents/reports/V3_PostMortem_Permission_Error.md (Original detailed analysis)

## Lessons Learned
- **Fail Fast:** Security components (like Guards) should fail immediately if their dependencies (Transaction) are missing, rather than degrading to a restrictive mode that confuses users.
- **Explicit is Better:** Implicit context contexts across FFI boundaries are fragile. Explicit passing of handles is safer.
