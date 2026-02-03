---
id: INC-009
title: Parallel Interpreter "Dead On Arrival"
area: core
severity: critical
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-009: Parallel Interpreter "Dead On Arrival"

## Summary
When attempting to run `engine.execute(func, parallel=True)` in Python 3.14 with Sub-interpreters, the system crashed or produced unexpected `ImportError` / `RuntimeError`. The Rust Core (`theus_core`) failed to load in worker interpreters due to tooling limitations, blocking the "Zero Trust" auditing features essential to the framework's promise.

## Background
Theus Architecture relies on `theus_core` (written in Rust) to act as the "Single Source of Truth" and "Auditor". The Parallel Execution model was designed to spawn Sub-interpreters where each interpreter would load its own instance of `theus_core` to perform local auditing before committing results.

## What Went Wrong
*   **Symptom:** Worker threads could not load `theus_core`.
*   **Result:** Parallel tasks failed silently or crashed the process.
*   **Error:** `ImportError: module ... does not support loading in subinterpreters`.

## Root Cause
### 1. The "Visa" Problem (PyO3)
The Rust Core was technically correct (thread-safe), but the binding layer (`pyo3` v0.23.3) did not generate the `Py_MOD_MULTIPLE_INTERPRETERS_SUPPORTED` slot required by CPython 3.14. CPython refused to load the module in sub-interpreters to prevent potential memory corruption.

### 2. Logical Coupling
The initial design assumed `theus_core` MUST exist in every interpreter to handle auditing locally. This created a hard dependency that failed when the module was blocked.

## Resolution
We implemented the **"One Brain, Many Hands" (Architectural Decoupling)** model:

### Rust Actions
*   Refactored `AuditSystem` to use **Process-Global Shared State** (`src/globals.rs`) via `OnceLock`. This prepares the ground for native support in the future.

### Python Actions
*   Implemented **Soft Fallback** in `structures.py`: If `theus_core` fails to load (in a Worker), fallback to Pure Python stubs.
*   **Supervisor Logic:** The Main Process (which *has* Rust Core) acts as the Supervisor. It intercepts the `StateUpdate` result from the Worker and performs the **Audit & Commit** using the Rust Core.

## Verification
*   **Test Suite:** `tests/parallel_suite/test_subinterpreter_resilience.py` (ALL PASS).
*   **Proof of Concept:** `tests/parallel_suite/test_arch_claims.py` confirmed that Rust Core correctly BLOCKS execution when failure thresholds are exceeded.

## Lessons Learned
*   **Toolchain Maturity:** Bleeding edge features (Sub-interpreters) often lack tooling support (PyO3).
*   **Decoupling:** designing for "Capability Degradation" (Soft Fallback) is crucial for resilience.
