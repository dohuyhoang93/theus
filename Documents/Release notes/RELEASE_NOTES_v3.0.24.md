# Release Notes v3.0.24

**Release Date:** 2026-03-04
**Author:** Do Huy Hoang ([@dohuyhoang93](https://github.com/dohuyhoang93))

---

## Overview

Version 3.0.24 is a **Testing & Stability** release. It adds 85 new tests for the Flux DSL and async orchestrator, fixes a critical infinite-loop bug in the Rust workflow engine, resolves COW deepcopy crashes in the report pipeline, and fixes the scaffold demo project.

---

## Bug Fixes

### [INC-021] Flux DSL Safety Trip Fails to Catch Empty While Loops (Critical)

**Problem:** When a `flux: while` loop had an empty `do: []` block, the `ops_counter` never incremented because it only counted inside the step iterator (`for step in steps`). This caused the program to hang indefinitely with no error or timeout.

**Fix (Plan C — A + B combined):**
- **(A) Runtime:** Added `ops_counter` increment and Safety Trip check directly inside the `while` loop body in `fsm.rs`, before calling `execute_steps`.
- **(B) Parser:** Added `[FLUX-WARN]` warnings when the parser encounters empty `do:`, `then:`, `else:`, or `steps:` blocks.

**File:** `src/fsm.rs`

---

### [INC-020] Transaction Object Leaks into Data Graph, Crashes COW Deepcopy (High)

**Problem:** ContextGuard's COW deepcopy encountered non-copyable Transaction objects embedded in the data graph, raising `RuntimeError: cannot deepcopy`. This blocked the entire post-experiment report pipeline (aggregate → plot → save).

**Fix:**
- **`context_helpers.py`:** Reordered resolution priority — `_inner._target` (no COW) first, dict-like access (triggers COW) as last-resort fallback with `RuntimeWarning` suppressed.
- **`p_plot_results.py`:** Added `matplotlib.use('Agg')` to prevent tkinter GUI-threading crashes on worker threads.

**Note:** Root cause was already fixed in Rust Core v3.3 — `SupervisorProxy` no longer stores Transaction refs (uses `is_mutable: bool` flag + `contextvars` lookup instead).

**Files:** `context_helpers.py`, `p_plot_results.py`, `p_save_summary.py`, `p_aggregate_results.py`

---

### Scaffold Demo: `ctx.log.info()` → `ctx.log()`

**Problem:** Scaffold processes called `ctx.log.info(...)` but `ContextGuard.log()` is a method that takes a string directly, not a Python logger object.

**Fix:** Updated all scaffold processes (`ecommerce.py`, `async_outbox.py`) to use `ctx.log("message")`.

**Files:** `theus/scaffold/src/processes/ecommerce.py`, `theus/scaffold/src/processes/async_outbox.py`

---

## New Tests (85 total)

### Flux DSL 4-Case Test Suite (68 tests, 5 files)

| File | Tests | Scope |
|------|-------|-------|
| `test_flux_if_4case.py` | 13 | If/else branching |
| `test_flux_while_4case.py` | 12 | While loops, Safety Trip |
| `test_flux_fsm_4case.py` | 10 | FSM state transitions |
| `test_flux_parser_4case.py` | 11 | YAML parsing, edge cases |
| `test_flux_integration_4case.py` | 7 | End-to-end workflows |

### Execute Async Test Suite (17 tests, 2 files)

| File | Tests | Scope |
|------|-------|-------|
| `test_flux_async_4case.py` | 9 | `WorkflowEngine.execute_async` (Rust direct) |
| `test_workflow_async_4case.py` | 8 | `TheusEngine.execute_workflow` (non-mock integration) |

**Testing Methodology:** All tests follow the 4-case coverage pattern:
1. **Standard** — typical usage
2. **Related** — cross-feature interaction
3. **Boundary** — edge cases and limits
4. **Conflict** — error handling and contradictory inputs

---

## Verification

```
cargo clippy -- -D warnings   → 0 warnings
ruff check .                   → All checks passed
pytest (full suite)            → ALL GREEN
Local CI                       → 🎉 COMPLETED SUCCESSFULLY
Scaffold (3 scenarios)         → E-Commerce ✅ | Async Outbox ✅ | Parallel ✅
Benchmarks (6 files)           → All passed
Sanity experiment              → 0 warnings, exit code 0
```

---

## Upgrade

```bash
pip install theus==3.0.24 --upgrade
```
