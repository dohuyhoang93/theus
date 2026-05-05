---
id: INC-027
title: commit_state Exported via #[pymethods] — Python-Callable OCC Bypass in TheusEngine
area: core
severity: high
introduced_in: v3.0 (PyO3 Transaction architecture)
fixed_in: v3.0.27
status: resolved
---

# INC-027: commit_state Exported via #[pymethods] — Python-Callable OCC Bypass in TheusEngine

## Summary

`fn commit_state(&mut self, state: Py<State>)` was exported via `#[pymethods]` on `TheusEngine`
without documentation, visibility marker, or access guard. This made the method callable from
Python via two independent paths: `engine._core.commit_state(state)` and
`engine.commit_state(state)` (via `__getattr__` delegation). Both paths performed a raw assignment
of `self.state = state` with **no version check, no OCC validation, no schema enforcement, and no
audit logging** — allowing any caller to silently overwrite engine state at any version, discarding
concurrent writes without conflict detection.

The root cause is not a deliberate design decision but a structural coupling artifact: the Rust
`Transaction::__exit__` needed to commit a new state object into the engine after completing its
OCC pipeline, and the only available mechanism was a Python-level method call via
`engine.call_method1("commit_state", ...)`. This forced `commit_state` to exist in `#[pymethods]`
— making it reachable from Python as a side effect of an internal implementation detail.

## Background

Theus enforces Optimistic Concurrency Control (OCC) via `compare_and_swap()`: any state write must
pass a version check, optional schema validation, and conflict detection before the new state is
committed. The canonical commit path is:

```
Transaction.__exit__
  → OCC version check          (conflict guard)
  → State.update()             (CoW new state object)
  → schema validation          (Pydantic, opt-in)
  → commit new state           ← THIS is where commit_state was called
  → publish_signals()          (INC-023 fix: fires AFTER commit)
```

`Transaction` and `TheusEngine` are two separate `#[pyclass]` structs. In PyO3, two `#[pyclass]`
objects cannot call each other's Rust methods directly without going through the Python object
layer. Therefore, when `Transaction::__exit__` (Rust) needed to write the validated state back
into `TheusEngine` (Rust), it used:

```rust
engine.call_method1("commit_state", (new_state_obj,))?;
```

This is **stringly-typed dynamic dispatch** — equivalent to `getattr(engine, "commit_state")(...)`.
It bypasses Rust's type system entirely and requires `commit_state` to be a `#[pymethod]`.

## What Went Wrong

`commit_state` was exported as a public Python method with no guards, no documentation of its
danger, and no indication it was intended to be internal. The `TheusEngine.__getattr__` delegation
(`return getattr(self._core, name)`) made it accessible on the Python wrapper class as well.

Two access paths existed simultaneously:

| Path | Syntax | Mechanism |
|------|--------|-----------|
| Direct Rust object | `engine._core.commit_state(state)` | PyO3 method on `TheusEngine` |
| Via `__getattr__` | `engine.commit_state(state)` | Python wrapper delegation to `_core` |

Both paths executed identical code: `self.state = state` — raw field assignment, zero validation.

**Exploit scenario (silent data corruption):**

```python
engine = TheusEngine()

with engine.transaction() as tx:
    tx.update(data={"balance": 1000})
# state.version = 1, balance = 1000

stale = engine._core.state  # capture version 1

with engine.transaction() as tx:
    tx.update(data={"balance": 2000})
# state.version = 2, balance = 2000

# Silent rollback — no exception, no warning, no audit entry
engine._core.commit_state(stale)
# state.version = 1, balance = 1000
# All writes since stale capture are silently discarded
```

The method was also used in test scaffold code (`tests/02_safety/repro_deadlock_abba.py` lines 49
and 105) as a convenience mechanism to seed initial state, establishing a pattern that could
propagate to production code.

## Impact

- **Any Python code** with access to an engine instance could silently overwrite state to any
  prior version, bypassing OCC, schema validation, audit logging, and conflict detection
- **`engine._core` access restriction** was the only nominal barrier — but `_core` is a
  convention, not an enforced visibility boundary in Python
- **`__getattr__` delegation** made `engine.commit_state(state)` callable without even needing to
  know about `_core`
- **Test scaffold usage** (`repro_deadlock_abba.py`) normalized the pattern, increasing the risk
  of it being copied into production processes
- **No test existed** that verified `commit_state` was NOT callable from Python — the risk was
  invisible to the test suite

**Severity: High** — The vulnerability required knowing the internal API, but the method appeared
in the `.pyi` stub file (`theus_core.pyi:138: def commit_state(self, /, state): ...`), making it
discoverable via type hints and autocomplete in any editor.

## Root Cause

### Micro (Code Level)

```rust
// src/engine.rs — BEFORE fix
#[pymethods]
impl TheusEngine {
    fn commit_state(&mut self, state: Py<State>) {
        self.state = state;  // raw assignment — no pub, no doc, no guard
    }
    // ...
}

// Transaction::__exit__ — forced the above to exist
engine.call_method1("commit_state", (new_state_obj,))?;
// stringly-typed call: bypasses Rust type system,
// requires commit_state to be in #[pymethods]
```

`fn commit_state` has no `pub` modifier, no `#[pyo3(name = "...")]` annotation, and no doc
comment — all signals that it was not intended as a user-facing API. It was exported
unintentionally as a side effect of the `call_method1` coupling.

### Macro (Architecture Level)

The root structural cause is that `Transaction` and `TheusEngine` are two separate `#[pyclass]`
structs with no direct Rust-to-Rust communication channel. In PyO3, `#[pyclass]` objects interact
through the Python object layer by design. This creates a forced choice:

1. Keep both as `#[pyclass]` → require `call_method1` for cross-struct calls → force `commit_state`
   into `#[pymethods]` → expose the bypass
2. Merge Transaction into TheusEngine → loses the clean separation between transaction context and
   engine state
3. Extract a shared Rust struct that both can access natively → correct long-term architecture, but
   requires deeper refactor

The v3.0.27 fix chose option 3 (partial): `Transaction::__exit__` now borrows `TheusEngine` via
`engine.borrow_mut()` and assigns `state` directly as a Rust field, removing the need for
`call_method1` entirely:

```rust
// src/engine.rs — AFTER fix
{
    let mut engine_ref = engine.borrow_mut();
    engine_ref.state = new_state_obj.extract::<Py<State>>()?;
}
```

This is type-safe, verifiable by the Rust compiler, and requires no Python method export.

## Why This Was Hard to Detect

1. **The `.pyi` stub file documented it** — `commit_state` appeared in autocomplete, giving the
   false impression it was an intentional public API
2. **`__getattr__` delegation is a blanket forwarder** — any Rust method not explicitly blocked
   appears as a first-class attribute of `TheusEngine` at runtime
3. **The test that confirmed the bypass existed in the same file that should have caught it** —
   `verify_parity_gap_methods.py` had `test_conflict_case_direct_commit_bypasses_occ` which
   verified the bypass *worked*, not that it was prevented
4. **Test scaffold usage normalized the pattern** — seeing `engine._core.commit_state(state)` in
   `repro_deadlock_abba.py` made it look like an accepted idiom
5. **No "must not be callable" test existed** — the absence of a negative assertion left the
   vulnerability invisible to CI

## Resolution

### Changes in v3.0.27

**`src/engine.rs`** (primary fix):
- Removed `fn commit_state` from `#[pymethods]` impl block entirely
- Replaced `engine.call_method1("commit_state", (new_state_obj,))?` in `Transaction::__exit__`
  with direct Rust borrow:
  ```rust
  {
      let mut engine_ref = engine.borrow_mut();
      engine_ref.state = new_state_obj.extract::<Py<State>>()?;
  }
  ```

**`theus/theus_core.pyi`**:
- Removed `def commit_state(self, /, state): ...` from `TheusEngine` stub

**`tests/02_safety/repro_deadlock_abba.py`**:
- Replaced both `engine._core.commit_state(state)` seed calls with the standard transaction path:
  ```python
  with engine.transaction() as tx:
      tx.update(data=initial_data)
  ```
- Removed `from theus_core import State` import (no longer needed)

**`tests/verify_parity_gap_methods.py`**:
- Updated `_make_engine_with_core_state()` helper to use transaction-based seeding
- Converted `test_conflict_case_direct_commit_bypasses_occ` and
  `test_via_getattr_delegation_same_bypass_risk` from bypass-confirmation tests to
  bypass-prevention tests (`assertRaises(AttributeError)`)
- Updated `test_commit_state_must_be_classified_as_high_risk` to verify the method is no longer
  accessible via either path
- Removed `commit_state` from GAP_METHODS lists (7 → 6 methods)

## Long-Term Changes

**New invariant:** `Transaction::__exit__` must never call `TheusEngine` internal state mutations
through `call_method1`. Any cross-struct mutation in the commit path must use direct Rust borrow.

**Architecture rule:** Methods that are Rust-internal commit primitives must NOT appear in
`#[pymethods]`. If a Rust struct needs to mutate another `#[pyclass]` after OCC validation, the
correct approach is `borrow_mut()` field assignment, not exported method call.

**Stub hygiene:** `theus_core.pyi` must only contain methods that are intentionally part of the
public API. Internal-only methods removed from `#[pymethods]` must be simultaneously removed from
the stub.

## Preventive Actions

1. **Test (added):** `test_commit_state_must_be_classified_as_high_risk` now asserts
   `hasattr(engine, "commit_state") == False` and `hasattr(engine._core, "commit_state") == False`
2. **Test (added):** Bypass tests now assert `AttributeError` rather than confirming bypass works
3. **Code review rule:** Any new `fn` added to `#[pymethods]` without `pub` visibility AND without
   doc comment should trigger a review question: "Is this intentionally user-facing?"
4. **Stub review:** `theus_core.pyi` should be reviewed against `#[pymethods]` at each release
   to ensure no internal-only methods are accidentally documented as public API
5. **`__getattr__` audit:** `TheusEngine.__getattr__` delegation is still a porous boundary;
   future work should consider an explicit allowlist (`_ALLOWED_DELEGATED_METHODS`) to prevent
   new accidental exports

## Related

- INC-023: Signal Publish Timing Gap (related: both were forced by `Transaction::__exit__` design)
- `tests/verify_parity_gap_methods.py`: Investigation file that documented the bypass behavior
- `tests/02_safety/repro_deadlock_abba.py`: Test that used `commit_state` as scaffold pattern

## Lessons Learned

1. **A method required by an internal caller is not automatically safe to expose externally.**
   The correct fix is to change how the internal caller works, not to add guards to the exposed
   method.

2. **Stringly-typed cross-struct calls (`call_method1("name", ...)`) are a code smell in PyO3.**
   They bypass the type system, force methods into `#[pymethods]`, and create hidden coupling
   between internal and public APIs. Prefer `borrow_mut()` direct field access.

3. **A test that proves a vulnerability *works* is not a security test.**
   `test_conflict_case_direct_commit_bypasses_occ` confirmed the bypass — it should have been a
   test that the bypass raises an error. "Document the bad behavior" is not the same as "prevent
   the bad behavior."

4. **Stub files are API documentation.** Anything in `.pyi` will be treated as intentional public
   API by users, IDEs, and type checkers. Unintentional exports in `#[pymethods]` must be removed
   from both the Rust impl and the stub simultaneously.

5. **`__getattr__` delegation creates an implicit public surface.** The Python wrapper's
   `return getattr(self._core, name)` transparently forwards every Rust method — including
   dangerous internals. An allowlist or explicit block is stronger than relying on callers knowing
   which methods are "private."
