---
id: INC-028
title: Transaction.__exit__ Had No OCC — Silent Lost Updates on Concurrent Writes
area: core
severity: medium
introduced_in: v3.3 (deliberate decoupling of compare_and_swap from Transaction.__exit__)
fixed_in: v3.0.27 (same release cycle as INC-027)
status: resolved
---

# INC-028: Transaction.__exit__ Had No OCC — Silent Lost Updates on Concurrent Writes

## Summary

`Transaction.__exit__` performed a blind last-writer-wins commit with no version check, no conflict
detection, and no error raised on overlap. Any process containing an internal `await` point
could silently overwrite a concurrent commit that occurred during its execution window.
The `execute()` retry loop — designed for exactly this failure mode — was structurally unreachable
because `__exit__` never produced the `"CAS Version Mismatch"` string that the loop monitored.

The root cause was a deliberate v3.3 architectural decision: `compare_and_swap` was removed from
the `Transaction.__exit__` path to eliminate a "double-bump" regression (two version increments
per commit). The decoupling removed the OCC gate but no replacement was implemented, leaving
`Transaction.__exit__` as a raw state replace with no protection.

## Background

Theus OCC model has two commit paths:

| Path | Version Check | Error on Conflict | Retry-Triggerable |
|------|-------------|-------------------|-------------------|
| `compare_and_swap()` | Yes — explicit `expected_version` param | `ContextError("CAS Version Mismatch")` | Yes |
| `Transaction.__exit__` (pre-fix) | **None** | **None** | **Never** |

`Transaction.__exit__` was the standard path used by every call to `engine.execute()`.
`compare_and_swap()` was a lower-level escape hatch for explicit OCC contracts.

The `execute()` retry loop (`theus/engine.py`) monitored two error strings:

```python
is_cas_error  = "CAS Version Mismatch" in err_msg
is_busy_error = "System Busy" in err_msg
```

Both strings were only reachable if the *process body* explicitly called `compare_and_swap()` or
triggered VIP lockout. For processes that simply read and return state — the vast majority of
production use — neither string was ever generated, and the retry loop never fired.

The v3.3 comment that explains the decoupling (still present as a source comment):

```python
# [v3.3 FIX] RELY ON Transaction.__exit__ for Atomic Commit
# Do NOT call compare_and_swap here, as it causes double-bumps
```

## What Went Wrong

### Structural Gap

`Transaction.__exit__` called `State.update()` on `current_state_obj` obtained via
`engine.getattr("state")` — which reads the **live, current** state at commit time, not a snapshot
captured at open time. No `start_version` was recorded during `__enter__`. No comparison was made
between the version at open and the version at commit.

```rust
// BEFORE FIX — Transaction::__enter__
fn __enter__(mut slf: PyRefMut<Self>, _py: Python) -> PyResult<Py<Self>> {
    slf.start_time = Some(Instant::now());  // only start_time, no version
    Ok(slf.into())
}

// BEFORE FIX — Transaction::__exit__ (simplified)
let current_state_obj = engine.getattr("state")?;   // live read
// ... infer_shadow_deltas, commit ...
let new_state_obj = current_state_obj.call_method("update", ...)?;  // no OCC gate
engine_ref.state = new_state_obj.extract()?;         // raw assign
```

### Manifestation Condition

The bug only manifests when a process has an internal `await` yield point:

```python
@process(inputs=["domain.counter"], outputs=["domain.counter"])
async def increment(ctx):
    current = int(ctx.domain.counter)     # reads 0
    await asyncio.sleep(0)                # YIELD — other task commits 1
    return current + 1                    # commits 1, overwrites the committed 1
```

Without an internal `await`, asyncio executes the process body synchronously to completion before
switching — no interleave, no conflict. This is why the existing test suite passed: all
`test_case4` stress tests used compute-only processes with no `await` inside the body.

### The Double-Bump Problem (Why It Was Hard to Re-Add)

The v3.3 fix removed `compare_and_swap` because calling it from `__exit__` produced two version
bumps per commit:

1. `State.update()` increments version (inside `compare_and_swap`)
2. `commit_state()` stored the result → but if called again it would double-count

The correct fix was **not** to re-add `compare_and_swap` (which wraps the full commit path) but to
extract only the **version-check and field-level conflict gate** from `compare_and_swap`, and apply
it *before* the existing `State.update()` call in `__exit__`.

## Impact

- **Who**: Any production code using `engine.execute()` with I/O-bound processes (HTTP, DB, file,
  `asyncio.sleep`, inter-service calls)
- **What broke**: Concurrent writes to the same field silently produced lost updates. No exception,
  no audit trail, no retry. The process with the latest commit time "won" regardless of logical
  ordering.
- **Severity downgrade from HIGH to MEDIUM**: The bug is latent, not active. asyncio's
  single-thread model serializes compute-only processes — the most common Theus use case — without
  interleave. Only I/O-bound processes with internal `await` are actually exposed.
- **Retry infrastructure**: `ConflictManager`, `retries=N`, backoff — all functional but never
  triggered by the standard path. Dead code in practice.

## Root Cause

### Micro (Mental Model — Integrative Critical Analysis)

The v3.3 fix applied a **local patch to a symptom** (double-bump) without auditing the **contract
it was invalidating** (OCC guarantee on `__exit__`). The implicit assumption was:
*"removing compare_and_swap removes double-bumps without removing OCC"* — which is false because
`compare_and_swap` **was** the OCC gate. Removing it removed both the symptom and the protection.

The engineer who fixed the double-bump and the engineer who designed the OCC model were operating
on different mental models of the same function. The comment
`"# Do NOT call compare_and_swap here"` documented what was removed, not what was supposed to
replace it. This is a classic "solution orphan": a constraint is removed to fix X, but the
constraint also enforced Y, and Y is silently lost.

### Macro (System Structure — Systems Thinking)

The OCC model had no structural enforcement mechanism. There was no invariant test verifying
that `Transaction.__exit__` must raise `ContextError` on concurrent writes to the same field.
The CI suite had:
- Tests for compute-only concurrency (pass: serialize naturally)
- Tests for `compare_and_swap` OCC (pass: explicit API)
- No tests for I/O-bound `Transaction` OCC (the actual gap)

The feedback loop was broken: a regression in OCC behavior was not detectable from any existing
green test. The latency of the bug (only manifests under I/O-bound concurrency) meant no user
report was ever generated. Invisibility enabled persistence.

## Why This Was Hard to Detect

1. **asyncio serialization masks it**: Compute-only processes never interleave. The entire existing
   test suite used compute-only processes. CI was green the whole time.
2. **Silent failure mode**: Lost updates produce no exception, no log entry, no audit trail.
   The system continues operating "normally" — just with the wrong value.
3. **Misleading retry infrastructure**: The presence of `ConflictManager`, `retries=N`, and the
   retry loop created a false sense of protection. The infrastructure existed but was never
   reachable from the standard commit path.
4. **Comment concealed the gap**: The v3.3 comment explained what was *removed* but said nothing
   about what should *replace* it. A reader without full context would assume the fix was complete.
5. **Virtue audit needed**: Initial analysis (pre-audit) inflated severity to HIGH and recommended
   immediate implementation. Intellectual Virtue Audit (Filter A: Humility) correctly downgraded to
   MEDIUM and identified that the bug is latent, not active.

## Resolution

### Rust: `src/engine.rs`

**1. Added `start_version: u64` to `Transaction` struct:**

```rust
pub struct Transaction {
    // ...
    start_time: Option<Instant>,
    start_version: u64,          // [INC-028] OCC baseline captured at __enter__
    write_timeout_ms: u64,
    // ...
}
```

**2. `Transaction::__enter__` captures version at open:**

```rust
fn __enter__(mut slf: PyRefMut<Self>, py: Python) -> PyResult<Py<Self>> {
    slf.start_time = Some(Instant::now());
    // [OCC] Capture state version at transaction open — baseline for conflict detection
    let engine = slf.engine.bind(py);
    let engine_borrow = engine.borrow();
    slf.start_version = engine_borrow.state.bind(py).borrow().version;
    drop(engine_borrow);
    Ok(slf.into())
}
```

**3. `Transaction::__exit__` applies field-level OCC check after `commit()`, before `State.update()`:**

```rust
// [OCC] Field-level conflict detection (Smart CAS — same policy as compare_and_swap).
if self.start_version > 0 {
    let conflict = {
        let engine_borrow = engine.borrow();
        let current_state = engine_borrow.state.bind(py).borrow();
        let current_version = current_state.version;

        if current_version == self.start_version {
            None
        } else {
            // Field-level check: any pending field modified after start_version?
            let mut safe = true;
            'outer: for (zone_k, zone_v) in self.pending_data.bind(py).iter() {
                // ... key_last_modified check per field ...
                if *last_ver > self.start_version { safe = false; break 'outer; }
            }
            if safe { None } else { Some((self.start_version, current_version)) }
        }
    };

    if let Some((expected, found)) = conflict {
        return Err(ContextError::new_err(format!(
            "CAS Version Mismatch (Conflict Detected): Expected {expected}, Found {found} (Keys Changed)"
        )));
    }
}
```

This reuses the exact same smart-CAS logic from `compare_and_swap` (field-level overlap check).
Disjoint-field concurrent writes still merge safely (no false positives).

### Python: `theus/engine.py`

**4. Outer `try/except ContextError` wraps `with _tx_ctx as tx:` in `execute()`:**

Commit-time OCC errors from `__exit__` now propagate outside the inner `try/except` block (which
only catches *process body* exceptions). The outer handler applies the same retry policy:

```python
try:
    with _tx_ctx as tx:
        try:
            result = await self._attempt_execute(func, tx, *args, **kwargs)
            # ...
        except Exception as e:
            # ... existing body-level error handler ...
except ContextError as commit_err:
    # Transaction.__exit__ raised OCC conflict at commit time
    if "CAS Version Mismatch" in str(commit_err) or "System Busy" in str(commit_err):
        # Apply same retry policy: ConflictManager + current_retries < max_retries
        if should_retry:
            await asyncio.sleep(backoff_ms / 1000.0)
            continue
    raise commit_err
```

**5. `ContextError` imported from `theus.structures`.**

**6. False comment corrected:**

```python
# BEFORE: # NOTE: Transaction.__init__ calls deepcopy on state.data for snapshot isolation.
# AFTER:  # NOTE: Transaction captures start_version at __enter__ for OCC conflict detection.
#         # Read-Committed semantics (not MVCC snapshot): reads see latest committed data.
#         # On field-level conflict, __exit__ raises CAS Version Mismatch -> triggers retry below.
```

## Verification

Test file: `tests/verify_transaction_occ_gap.py` — 15 tests, all pass post-fix.

Key behavioral changes verified:

| Test | Pre-fix | Post-fix |
|------|---------|---------|
| `test_a3` — same-field concurrent commit | silent overwrite | `CAS Version Mismatch` raised |
| `test_a4` — 2 concurrent increments from 0 | final=1 (lost update) | final=2 (OCC + retry) |
| `test_a5` — disjoint fields (a/b) | both survive | both survive (no regression) |
| `test_a6` — 5 concurrent same-field | 5 executions, last-writer-wins | retries fired, all succeed |
| `test_b2` — `__exit__` raises CAS? | never | always on overlap |
| `test_b3` — retries=3 fires? | no (execution_count==3) | yes (execution_count>3) |
| `test_b4` — retries=0 vs 3 identical? | yes (both=lost update) | both converge correctly |
| `test_c2` — 5 external bumps, commit? | silent success | `CAS Version Mismatch` raised |

## Long-Term Changes

- `Transaction.start_version` is now an internal OCC baseline. It is intentionally **not exposed**
  as a Python attribute (no `#[pyo3(get)]`). It is an implementation detail, not an API contract.
- `Transaction.__exit__` now guarantees: if two concurrent processes write the same field, at most
  one commits on first attempt. The other receives `ContextError` and is retried by `execute()`.
- Smart-CAS (field-level, not version-level) is preserved: disjoint-field concurrent commits still
  merge without error. This is the intended behavior for independent subsystems sharing state.

## Preventive Actions

1. **Test coverage gap closed**: `tests/verify_transaction_occ_gap.py` now contains I/O-bound
   concurrent process tests (with internal `await asyncio.sleep(0)`) as the canonical regression
   guard for this class of bug.
2. **Convention rule**: Any future refactor of `Transaction.__exit__` commit path MUST verify
   `test_a3`, `test_a4`, `test_b2`, `test_b3` still pass before merging.
3. **OCC contract documented**: The invariant is now explicit — `Transaction.__exit__` MUST raise
   `ContextError("CAS Version Mismatch")` when `pending_data` contains a field whose
   `key_last_modified[field]` exceeds `start_version`.
4. **Virtue audit embedded in process**: Future severity/urgency assessments should apply
   Intellectual Humility (Filter A) before escalating latent bugs to "implement immediately".

## Related

- INC-027: `commit_state` OCC Bypass — predecessor incident; fixed the export gap that was a
  related structural enabler
- `tests/verify_transaction_occ_gap.py`: Reproduction + regression suite (15 tests)
- `src/engine.rs`: `Transaction` struct, `__enter__`, `__exit__` (field-level OCC block)
- `theus/engine.py`: `execute()` — outer `except ContextError as commit_err` handler

## Lessons Learned

1. **Removing a protection to fix a symptom requires naming a replacement.** The v3.3 double-bump
   fix was correct, but removing `compare_and_swap` required explicitly documenting which part of
   the OCC contract was now the responsibility of a different mechanism.

2. **A green CI does not prove a guarantee is upheld.** It only proves the tests that exist pass.
   Test coverage of *concurrent I/O-bound processes* was absent. The guarantee was never tested.

3. **Silent failure modes are the most dangerous.** Lost updates produce no exception. Any
   monitoring or alerting that relies on errors being raised will never detect them.

4. **Infrastructure existence ≠ infrastructure reachability.** `ConflictManager`, `retries=N`,
   and backoff were all correctly implemented but structurally unreachable from `__exit__`.
   "Working infrastructure" and "reachable infrastructure" are different claims.

5. **Severity estimation needs humility.** Initial analysis declared HIGH severity. Virtue audit
   (Intellectual Humility) correctly identified the bug as latent under typical usage patterns.
   Overestimating severity leads to rushed fixes with higher regression risk.
