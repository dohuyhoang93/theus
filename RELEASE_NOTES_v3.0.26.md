# Release Notes v3.0.26

**Release Date:** 2026-05-04  
**Author:** Do Huy Hoang ([@dohuyhoang93](https://github.com/dohuyhoang93))

---

## Overview

Version 3.0.26 is a **Code Quality & Stability** release. It resolves four incidents (INC-022 through INC-025) introduced or uncovered during the v3.0.25 stabilization cycle, and eliminates all 99 `clippy::pedantic` lint errors that were previously suppressed globally in CI.

---

## Bug Fixes

### [INC-022] SignalHub COW Deepcopy Crash — Silent `RuntimeWarning` in CI (Medium)

**Problem:** When a process accessed `ctx.signal` inside `ContextGuard`, the COW (Copy-On-Write) shadow mechanism attempted to `copy.deepcopy()` the `SignalHub` Rust object, which is not picklable. This raised `RuntimeError: Transaction isolation failure`, which `guards.py` downgraded to a `RuntimeWarning` and re-raised. The warning was swallowed by a bare `except Exception: pass` in the test, making CI pass for the wrong reason while printing noise on every run.

**Root Cause:** The COW zone-bypass only checked for `heavy_*` prefix. The `signal` top-level slot holds a Rust-managed singleton (`SignalHub`) — not user data — and had no bypass.

**Fix:**
- `src/zones.rs`: Added `"signal"` and `"cmd"` as full-name zone identifiers (alongside `sig_*`/`cmd_*` prefix patterns), so `resolve_zone("signal")` returns `ContextZone::Signal`.
- `src/guards.rs` `apply_guard()`: Added Signal/Meta/Log zone bypass **before** the COW dict/list path — system infrastructure objects are returned as-is, never deepcopied.
- Test updated to use `pytest.raises((PermissionError, RuntimeError))` — bare `except Exception: pass` removed.

**Files:** `src/zones.rs`, `src/guards.rs`, `tests/02_safety/test_chapter_05_compliance.py`

---

### [INC-023] Signal Publish Fires Before Data Commit — No Ordering Guarantee (Medium)

**Problem:** `SignalHub.publish()` was called inside `State.update()`, which runs **before** schema validation and `compare_and_swap` confirmation. If schema validation failed, the data commit rolled back but the signal had already been broadcast. In high-contention retry loops (`max_retries > 1`), a single logical transaction could emit duplicate signals to downstream subscribers.

**Root Cause:** `State.update()` mixed two responsibilities: (a) populating `last_signals` latch (correct, needed by Flux DSL), and (b) calling `signal.publish()` (must be deferred until after commit).

**Fix:**
- `src/structures.rs`: Removed `signal.publish()` calls from `State.update()`. Added new `publish_signals()` method that performs the actual Tokio channel send.
- `src/engine.rs` `Transaction.__exit__()`: Added deferred dispatch — `commit_state()` first, then `committed_state.publish_signals(pending_signal)`. Signal now fires **after** data is committed.
- `src/engine.rs` `TheusEngine.compare_and_swap()`: Same deferred pattern applied.

**Files:** `src/structures.rs`, `src/engine.rs`

---

### [INC-024] Stale `__pycache__` Causes Spurious Pytest Warnings on Cloned Repos (Low)

**Problem:** `.pyc` bytecode files embed the compile-time absolute `co_filename`. When the project was cloned or moved to a different path, stale bytecode carried the old path into pytest warning output, producing noisy `PytestWarning` about mismatched source files that were unrelated to the actual test run.

**Fix:** Added `step_purge_pycache()` to `scripts/Local_CI.py` as a pre-test vaccine. It walks `tests/` and removes all `__pycache__` directories before each pytest run, forcing fresh bytecode compilation with the correct paths.

**Files:** `scripts/Local_CI.py`

---

### [INC-025] `ProcessPool` Lazy-Spawn Reports False ❌ Speedup on Windows (Low)

**Problem:** The parallelism verification script (`verify_parallel_execution.py`) reported `ProcessPool` speedup below the 1.2× threshold, producing a false ❌ result. Root cause: `ProcessPool` (spawn strategy) creates worker processes lazily — a single-task warmup only pre-spawned 1 worker. The 2nd worker spawned JIT during measurement, injecting ~1.5s Windows process-spawn overhead that collapsed apparent speedup from ~1.9× to ~1.12×.

**Fix:** Replaced single-task warmup with `asyncio.gather(*[engine.execute(...) for _ in range(warmup_concurrency)])` where `warmup_concurrency=2`. This forces both workers to spawn concurrently before the timed measurement begins.

**Files:** `tests/manual/verify_parallel_execution.py`

---

---

## Changes

### Clippy Pedantic — Full Compliance (99 errors eliminated)

**Problem:** `cargo clippy --all-targets --all-features -- -D warnings -W clippy::pedantic` produced 99 errors across the Rust codebase. These were silently suppressed in CI with 17 global `-A` flags, hiding real code-quality issues.

**Fix:** Audited every lint error across all 13 affected Rust files. Applied the minimal correct fix per site:
- `String` → `&str` for parameters not consumed (no heap allocation needed)
- `#[allow(clippy::...)]` at the exact call site for PyO3-constrained signatures (`#[pymethods]` protocol methods where `&self`, `PyObject` params, and `PyResult<T>` returns are required by the FFI boundary)
- `#[allow(clippy::cast_possible_truncation)]` narrowly placed around intentional `u128 → u64` cast in timeout enforcement
- Renamed `_wrap_result` → `wrap_result` (underscore prefix implied unused, but was a public helper)
- Fixed `needless_borrow` (`&key` → `key`) in `audit.rs` call sites after `String → &str` param changes

**Files modified:**

| File | Lints fixed |
|------|-------------|
| `src/conflict.rs` | `needless_pass_by_value`, `cast_possible_truncation`, `cast_sign_loss`, `cast_precision_loss` |
| `src/supervisor.rs` | `needless_pass_by_value` (4 methods) |
| `src/proxy.rs` | `manual_let_else`, `used_underscore_binding`, `doc_link_with_quotes`, `needless_pass_by_value`, `unused_self`, `unnecessary_wraps`; `_wrap_result` renamed |
| `src/audit.rs` | `needless_pass_by_value`, `needless_borrow` |
| `src/structures_helper.rs` | `doc_link_with_quotes`, `needless_pass_by_value` |
| `src/delta.rs` | `needless_pass_by_value` |
| `src/fsm.rs` | `needless_pass_by_value`, `manual_let_else`, `unnecessary_wraps` |
| `src/guards.rs` | `manual_let_else`, `needless_pass_by_value`, `unused_self`, `unnecessary_wraps` |
| `src/shm.rs` | `unused_self`, `unnecessary_wraps` |
| `src/shm_registry.rs` | `unused_self`, `manual_let_else` |
| `src/engine.rs` | `needless_pass_by_value`, `unnecessary_wraps`, `unused_self`, `used_underscore_binding`, `cast_possible_truncation` |
| `src/structures.rs` | `unused_self`, `unnecessary_wraps`, `needless_pass_by_value` |
| `src/config.rs` | `needless_pass_by_value` |

### CI: Reduced Global `#[allow]` Suppression Flags

**Before:** 17 `-A` flags in `scripts/Local_CI.py`  
**After:** 7 `-A` flags (only genuine tech debt requiring larger refactors)

**Removed flags** (now enforced):
- `needless_pass_by_value`
- `unnecessary_wraps`
- `unused_self`
- `manual_let_else`
- `used_underscore_items`
- `used_underscore_binding`
- `doc_link_with_quotes`
- `cast_possible_truncation`
- `cast_sign_loss`
- `cast_precision_loss`

**Remaining flags** (accepted tech debt):
- `missing_errors_doc`
- `missing_panics_doc`
- `match_same_arms`
- `items_after_statements`
- `unreadable_literal`
- `needless_continue`
- `only_used_in_recursion`

---

## Test Results

- **Rust tests:** 1 passed, 0 failed
- **Python tests:** 385 passed, 3 skipped, 0 failed
- **Clippy:** 0 errors, 0 warnings
- **Pyright:** 0 errors, 0 warnings
- **Ruff:** All checks passed

---

## No Breaking Changes

All Python and Rust public APIs are unchanged. The fixes are internal implementation improvements with no observable behavioral difference.
