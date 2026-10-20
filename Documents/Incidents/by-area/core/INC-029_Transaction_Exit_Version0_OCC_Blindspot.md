---
id: INC-029
title: Transaction.__exit__ OCC Guard Skipped at Version 0 — Residual OCC Bypass After INC-028
area: core
severity: high
fixed_in: v3.0.27
status: resolved
---

# INC-029: Transaction.__exit__ OCC Guard Skipped at Version 0 — Residual OCC Bypass After INC-028

> **Method and evidence status.** This report is the result of a critical review of INC-027 and
> INC-028 using the Paul-Elder frame (8 elements of thought × 9 intellectual standards).
> Verification was **static only**: direct reading of the working tree, plus the public GitHub
> commit history for `src/engine.rs` and `theus/engine.py`. No test was executed. The finding below
> is **partially verified** — the code path is confirmed by reading; the exploitability condition is
> stated together with its own residual uncertainty.

## Summary

`Transaction::__exit__` applies its field-level OCC check only inside a guard:
`if self.start_version > 0`. `TheusEngine::new` constructs its `State` with an explicit
`version = 0`. A transaction opened against an engine that has never committed therefore captures
`start_version = 0`, the guard evaluates false, and the commit proceeds as a **blind raw state
replacement** — no version check, no conflict detection, no error raised. That is the identical
failure mode INC-028 claimed to close.

The guard exists because `Transaction` initialises `start_version: 0` as a "not yet opened" sentinel.
The defect is a **sentinel/domain collision**: `0` is simultaneously the sentinel for "unset" and a
reachable, legitimate engine version.

## Background

Theus enforces Optimistic Concurrency Control (OCC). INC-028 restored OCC on the standard commit
path by:

1. `Transaction::__enter__` capturing `start_version` from the live engine state, and
2. `Transaction::__exit__` performing a **field-level smart-CAS** check (same policy as
   `compare_and_swap`) before `State.update()`, raising
   `ContextError("CAS Version Mismatch (Conflict Detected) … (Keys Changed)")` on a same-field
   overlap, which the retry loop in `execute()` is designed to catch.

INC-028 documented the resulting contract in unqualified terms:

> `Transaction.__exit__` now guarantees: if two concurrent processes write the same field, at most
> one commits on first attempt.

## What Went Wrong

The guard's condition is written against a sentinel rather than against observed state:

- `State::new` declares default `version=1`, **but** `TheusEngine::new` calls
  `State::new(None, None, None, 0, 1000, py)` — explicit `0`.
- Therefore a freshly constructed engine legitimately sits at version 0.
- `Transaction` also initialises `start_version: 0`, meaning "not opened".
- `__exit__` cannot distinguish the two, and resolves the ambiguity by **skipping the check**.

Consequence: on a never-committed engine, two transactions writing the same field both commit; the
later commit silently overwrites the earlier. The regression suite cannot see this — see
"Why This Was Hard to Detect".

## Impact

- **Who is affected:** callers that open a transaction against an engine whose state version is still
  0. That is the state of `theus_core.TheusEngine()` immediately after construction, and the state
  used by the project's own regression file, which builds transactions via
  `theus_core.Transaction(engine._core)`.
- **What breaks:** same-field concurrent writes produce silent lost updates instead of
  `CAS Version Mismatch`. No exception, no audit entry, no retry.
- **Reachability (corrected):** `TheusEngine()` with no context leaves `init_data = {}` —
  because `BaseSystemContext.to_dict()` returns `{}` when both `domain` and `global_ctx` are `None` — so
  the hydration `compare_and_swap(0, init_data)` never runs and the engine stays at version 0. The
  blind spot is therefore reachable through the **default constructor**, not only through the raw
  Rust class. Passing a non-empty context seeds version 0 → 1 and arms the guard.
- **Why this is serious:** INC-028's downgrade to MEDIUM rested on the argument that the OCC
  guarantee now holds and only the *likelihood* of overlap is low. This report challenges the
  premise, not the likelihood: on a fresh engine the guarantee does not hold at all, and the first
  pair of concurrent commits — the exact scenario every concurrency test is built to model — runs
  unwitnessed.

## Root Cause

### Micro

```
// src/structures.rs — State::new default
#[pyo3(signature = (data=None, heavy=None, signal=None, version=1, ...))]

// src/engine.rs — TheusEngine::new
let state = Py::new(py, State::new(None, None, None, 0, 1000, py)?)?;   // explicit 0

// src/engine.rs — Transaction::__enter__
slf.start_version = engine_borrow.state.bind(py).borrow().version;      // captures 0

// src/engine.rs — Transaction::__exit__
if self.start_version > 0 {                                             // skipped
    // field-level smart-CAS conflict detection
}
```

### Macro

The absence of any invariant test for the guard's own precondition. INC-028 verified the OCC *body*
and never verified the *reachability of the body* across the full domain of legal starting versions.
A guard placed at the entry of a correctness path inherits none of the verification given to that
path.

## Why This Was Hard to Detect

1. **The regression suite structurally avoids the boundary.** All three tests that exercise
   `__exit__` conflict detection bump the version *before* opening the transaction —
   `test_a3_exit_raises_cas_mismatch_on_same_field_concurrent_commit`,
   `test_b2_transaction_exit_raises_cas_version_mismatch_on_conflict` and
   `test_c2_transaction_enter_captures_version_and_detects_conflict` all begin with
   `engine._core.compare_and_swap(0, {...})`. Version 0 is therefore never used as a baseline.
2. **The wrapper path usually escapes.** `TheusEngine(context=...)` seeds via
   `compare_and_swap(0, init_data)`, so wrapper-mediated tests never reach the blind spot either.
3. **Silent failure mode.** A lost update raises nothing, so no monitoring based on errors can see it.
4. **An absolute guarantee in INC-028 discouraged boundary testing.** "At most one commits" reads as
   a closed question; a reviewer has no reason to test version 0.
5. **Artifact hygiene resolved.** The regression file previously carried the header
   *"Two HIGH-severity findings"* and pre-fix test names (e.g.
   `test_b2_transaction_exit_raises_cas_version_mismatch_on_conflict`); these have been cleaned up and
   aligned to post-fix regression guard conventions.

## Evidence (Static Verification)

| Claim | Source | Result |
|---|---|---|
| Engine state initialises at version 0 | `src/engine.rs`, `TheusEngine::new` | Confirmed — `State::new(None, None, None, 0, 1000, py)` |
| `State::new` default is 1, overridden by the engine | `src/structures.rs` | Confirmed — `version=1` in the `pyo3` signature |
| `__enter__` captures the live version | `src/engine.rs`, `Transaction::__enter__` | Confirmed |
| `__exit__` gates the OCC block on `start_version > 0` | `src/engine.rs`, `Transaction::__exit__` | Confirmed |
| Wrapper hydration | `theus/engine.py`, `TheusEngine.__init__` | Confirmed — runs only `if init_data:`; `TheusEngine()` leaves it empty, so version stays 0 |
| Suite has 15 tests; none opens a transaction at version 0 | `tests/verify_transaction_occ_gap.py` | Confirmed after the 2026-10-17 rename (15 tests; `TestTransactionExitOCC` / `TestCASRetryActive`); opening pattern of a3/b2/c2 unchanged |
| INC-028's "v3.3 removed CAS from `__exit__`" | public GitHub history for `theus/engine.py` | **Not established** — only 3 commits exist for that file; predecessor fetch truncated at 20 KB |

## Severity Rationale

The project has no written criteria for severity, and two incidents in this repository rate the same
impact class differently:

- **INC-001 / INC-021** (THEMA, `Transaction Snapshot Lag`) — silent sequential data loss,
  deterministic, no exception, tests falsely green — rated **HIGH**, with the explicit reasoning
  "Silent data loss. No error/exception. Tests falsely PASS."
- **INC-028** — silent lost update, no exception, the designated suite unable to detect it — rated
  **MEDIUM**, downgraded on the grounds of being *latent* rather than *active*.

Those two rules cannot both be canonical. Applying INC-001's rule — impact class and invisibility
dominate, likelihood does not downgrade — INC-028 should have been HIGH, and this incident is
**HIGH**. Applying a reachability-weighted rule, the discriminator is whether the defect is reachable
on a supported public path without special configuration; it is, because `TheusEngine()` is the
default constructor.

Either way: **HIGH**. The rating is provisional only in that it has not been reproduced by an
executed test; the code path is confirmed by reading.

## Resolution (proposed — not implemented)

The finding is open. Candidate fixes, in order of preference:

1. **Remove the sentinel.** Make `start_version: Option<u64>`; set it in `__enter__`; test
   `if let Some(v) = self.start_version` in `__exit__`. This eliminates the ambiguity structurally
   rather than by convention.
2. **Add an explicit opened flag** (`opened: bool`) and guard on that instead of on a version value.
3. **Raise the engine's initial version to 1** so that 0 can never be a legitimate baseline. Smallest
   change, but it leaves the sentinel collision latent for any future re-introduction of version 0.

Whichever option is chosen, the guard must fail **closed**: an unopened or unknown state must never
silently disable the conflict check.

## Long-Term Changes

- **New invariant:** every `Transaction` that reaches the commit path MUST have executed an OCC
  check. Disabling the check must not be expressible by a reachable state value.
- **Rule:** sentinel values must not overlap the domain of legitimate values. If a value can occur in
  production, it cannot also mean "unset".
- **Contract correction:** INC-028's guarantee should be restated with its precondition made
  explicit, or withdrawn until the precondition is enforced.

## Preventive Actions

1. **[added 2026-10-17 — currently red]** `tests/verify_occ_vulnerability_matrix.py` V1.1 probes
   a same-field concurrent commit opened at engine version 0. Static reading: it fails against the
   unfixed guard (`if self.start_version > 0` is still present in `src/engine.rs`) — the correct
   state for a regression proof before the fix.
2. **[resolved 2026-10-17]** The suite now implements all 14 vectors: V1.3 (default constructor +
   concurrent `execute()` at version 0), V2.3 and V3.2 were added, and V5.2 was renamed to
   `..._at_version_one_converge` with a context-seeded engine, removing the earlier version-0 setup
   flaw. All classes derive from `unittest.IsolatedAsyncioTestCase`, so one runner executes
   everything. Residual: V1.1 and V1.3 remain red until the guard fails closed
   (`src/engine.rs:651`). The suite itself is now internally consistent: 14 vectors matching the
   header, one runner, `BaseMatrixTestCase` resetting `NamespaceRegistry` between tests, and V1.3
   asserting `final_counter == 3` (a falsifiable lost-update check, not a vacuous range test).
3. **[x] Naming hygiene — completed 2026-10-17.** Nine test functions and two classes renamed in
   `tests/verify_transaction_occ_gap.py` (`TestTransactionExitOCC`, `TestCASRetryActive`); the obsolete
   "Two HIGH-severity findings" header was replaced with
   *"Regression Guard: Transaction.__exit__ OCC & CAS Retry Validation (INC-028)"*. This is cosmetic
   hygiene only — it does not close the version-0 gap, and actions 1–2 remain outstanding.
4. **Doc hygiene:** `pyproject.toml` and `Cargo.toml` report 3.0.26 and no `RELEASE_NOTES_v3.0.27.md`
   exists, while INC-027 and INC-028 both claim `fixed_in: v3.0.27`. Either cut the release or mark
   those fixes as unreleased.
5. **Review rule:** any `if` that gates a correctness check on a *value* rather than on an explicit
   state flag requires its own test covering the value that disables it.

## Related

- INC-001 / INC-021 (THEMA): `Transaction Snapshot Lag` — the HIGH-severity precedent this
  rating is aligned to
- INC-027: `commit_state` OCC Bypass — same root region (`Transaction::__exit__` as the commit
  boundary)
- INC-028: `Transaction.__exit__` Had No OCC — the fix this report audits
- `tests/verify_transaction_occ_gap.py` — the designated regression guard; cannot detect this case
- `src/engine.rs` (`TheusEngine::new`, `Transaction::__enter__`, `Transaction::__exit__`)
- `src/structures.rs` (`State::new`)

## Lessons Learned

1. **A value that can legitimately occur cannot also be a sentinel.** `0` meant both "not opened" and
   "a real engine version". The ambiguity was resolved in favour of *skipping the check* — the wrong
   direction for a safety guard.
2. **An absolute guarantee is a claim, not a verification.** "At most one commits" was never tested
   at its own boundary. A guarantee inherits the coverage of the tests written against it — no more.
3. **Guards need tests for the branch that disables them.** Testing the protected body is not testing
   the protection.
4. **When a fix is verified by a suite that shares its author's mental model, the boundary is the
   blind spot.** All 15 tests happened to avoid version 0; the omission was not random, it followed
   from how the fixtures were written.
5. **Silent failure modes survive green CI.** Nothing in the suite could fail, because nothing in the
   suite exercised the condition.

## Post-Implementation Verification (2026-10-20)

Executed on the working tree after the resolve plan was implemented. The compiled extension
(`theus_core.cpython-314-x86_64-linux-gnu.so`, 15:24) is newer than `src/engine.rs` (15:23), so the
suites ran against the new build rather than a stale artefact.

| Run | Command | Result |
|---|---|---|
| OCC vulnerability matrix | `pytest tests/verify_occ_vulnerability_matrix.py -q` | **17 passed** |
| INC-028 regression | `pytest tests/verify_transaction_occ_gap.py -q` | **15 passed** |
| Full suite | `pytest tests -q` | **490 passed, 3 skipped** |
| Rust check | `cargo check` | fails — PyO3 0.23.5 supports Python <= 3.13, env is 3.14.4 |
| Rust check (ABI3) | `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo check` | exit 0 |

The ABI3 compatibility variable is required in this environment. It should live in the build
script, not be passed ad hoc.

**Performance note (measured 2026-10-20, post-fix).** The full suite runs in **109.87 s**
against **45.61 s** on the pre-fix build — a 2.4x increase. The 1000-sequential-write burst test
(`test_case3_bien_burst_no_document_loss`) alone takes 23.4 s. The likely cause is the lazy
`_sync_registry_from_core()` executing on every version change: a growing state is re-validated once
per commit, making sequential writes quadratic in state size. Correctness is unaffected; latency is.
This should be tracked as a separate performance incident rather than blocking the correctness fix.
