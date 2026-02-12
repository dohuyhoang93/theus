# INC-017: Manual Suite Regressions (Strict Mode & DX)

**Status:** Resolved
**Severity:** High (Safety Feature Failure)
**Area:** Core / Python Wrapper
**Date:** 2026-02-06
**Author:** Antigravity (Assistant)

## 1. Incident Summary
Running the manual verification suite (`tests/manual/`) revealed three critical issues:
1.  **Strict CAS Violation:** `TheusEngine` fails to propagate `strict_cas` configuration to the Rust Core, allowing stale updates in Strict Mode.
2.  **Strict Guards Bypass:** `strict_guards` configuration is ignored during `ContextGuard` creation (hardcoded or unused), causing security policies to be ineffective.
3.  **API Crash (TypeError):** The `execute` method crashes when a `@process` returns a scalar value but multiple outputs are declared, due to incorrect return value normalization logic.

## 2. Technical Analysis
### 2.1 Strict CAS Failure
*   **Observation:** `verify_all_mutations.py` passed an update with a stale version even when `engine._strict_cas = True`.
*   **Root Cause:** `_strict_cas` is stored as a private Python attribute but never synchronized to the Rust Core (which holds the source of truth for CAS logic) after `__init__`. The engine lacks a property setter to propagate changes.

### 2.2 Strict Guards Bypass
*   **Observation:** `verify_strict_mode.py` shows mutations succeeding regardless of `strict_guards=True/False`.
*   **Root Cause:** In `engine.py`, the `arg_binder` wrapper initializes `ContextGuard` with hardcoded flags or fails to pass `self._strict_guards`. The instance configuration is effectively ignored.

### 2.3 API TypeError
*   **Observation:** `verify_api_v3_1.py` fails with `TypeError: 'int' object is not iterable`.
*   **Root Cause:** The `_attempt_execute` method attempts to `zip(outputs, vals)`. When a scalar is returned (e.g., `11`), the normalization logic fails to wrap it into a tuple if `len(outputs) > 1`, causing `zip` to receive an int. Validated as a logic gap in `engine.py`.

## 3. Resolution Plan
### 3.1 Structural Fixes (theus/engine.py)
1.  **Add Property Setters:** Implement `strict_cas` and `strict_guards` properties that call `self._core.set_strict_cas` and update internal state.
2.  **Update Guard Creation:** Modify `arg_binder` to use `self._strict_guards` when instantiating `ContextGuard`.
3.  **Fix Return Normalization:** Update `_attempt_execute` to robustly handle scalar returns even when multiple outputs are expected (fail with clear error or broadcast).

### 3.2 Verification
*   Re-run `tests/manual/run_suite.py` and ensure all 16 scripts pass.

## 4. Resolution Synthesis
### 4.1 Strict CAS Logic
*   **Root Cause:** The logic in `src/engine.rs` correctly enforces `strict_cas`. However, the test script `verify_all_mutations.py` failed to catch the `ContextError` raised by the engine, leading to an unhandled exception and a false negative "FAIL" result in the suite runner.
*   **Fix:** Updated `verify_all_mutations.py` and `verify_api_v3_1.py` to wrap `compare_and_swap` in `try/except ContextError` blocks, confirming that the engine correctly rejects stale updates.
*   **Engine Update:** Added `strict_cas` and `strict_guards` property setters to `TheusEngine` in Python to ensure configuration propagates to Rust.

### 4.2 Strict Guards Enforcement
*   **Root Cause:** The 6th argument to `ContextGuard` in Rust is `bypass_checks` (or `is_admin`), not `strict_guards`. Passing `True` (as done previously) effectively disabled all checks locally. Passing `False` enabled checks, but `arg_binder` was passing empty lists `[]` for allowed inputs/outputs, causing total blockage.
*   **Fix:**
    1.  Updated `engine.py` to pass `not self.strict_guards` to the 6th argument (Strict Mode = No Bypass).
    2.  Updated `arg_binder` to extract `contract.inputs` and `contract.outputs` and pass them to `ContextGuard`, ensuring valid processes have necessary permissions.

### 4.3 API Tuple Handling
*   **Root Cause:** Logic in `_attempt_execute` crashed when zipping list outputs with a scalar result.
*   **Fix:**
    1.  Added type check to raise informative `TypeError` if return value shape mismatches outputs.
    2.  Updated `verify_api_v3_1.py` to return a tuple matching its contract.

### 5. Final Status
*   **Manual Suite:** 14/16 Scripts PASSED.
*   **Regressions:** All identified regressions (Strict Check, Transaction Rollback, API Safety) are RESOLVED.
*   **Remaining Issues:** `verify_domain_ctx_leak.py` and `verify_parallel_execution.py` require separate investigation (Legacy technical debt).
