---
id: INC-022
title: SignalHub Cannot Be Deepcopied in COW Path — Swallowed Exception Creates Silent Warning
area: core
severity: medium
introduced_in: v3.0 (MVCC COW architecture)
fixed_in: v3.0.25
status: resolved
---

# INC-022: SignalHub Cannot Be Deepcopied in COW Path — Swallowed Exception Creates Silent Warning

## Summary

When a process declares `signal.ping` as an input and accesses `ctx.signal` inside ContextGuard, the engine's Copy-On-Write (COW) isolation mechanism attempts to `deepcopy` the `signal` slot, which contains the non-picklable Rust-backed `SignalHub` object. The deepcopy fails with `TypeError: cannot pickle 'theus_core.SignalHub' object`, which Rust wraps into `RuntimeError: Transaction isolation failure`, which Python's `ContextGuard.__getattr__` converts to a `RuntimeWarning` and re-raises. The test `test_claim_zone_enforcement_edge` catches the re-raised exception silently via `except Exception: pass`, making the CI run pass while leaving the warning unresolved and the test semantics incorrect.

## Background

Theus uses MVCC with a COW (Copy-On-Write) shadow mechanism: when a process first reads a data path, `engine.rs` calls `copy.deepcopy()` on that state subtree to create an isolated shadow. This works correctly for pure Python objects (dicts, lists) and is intentionally bypassed for Heavy Zone objects (`heavy_*` prefix).

`SignalHub` is a Rust-managed singleton object responsible for signal routing between processes. It lives at the `signal` path in the state graph — the same graph that COW traverses. Unlike Transaction (fixed in INC-020 / v3.3 Rust fix), `SignalHub` has no `__deepcopy__` bypass in either the engine or ContextGuard.

## What Went Wrong

Call chain when the test executes `await engine.execute("task_signal_input_allowed_relaxed")`:

```
ctx.signal.get("ping")
  → ContextGuard.__getattr__('signal')           # guards.py:290
    → engine.rs COW shadow creation
      → copy.deepcopy(SignalHub)                  # engine.rs:773
        → TypeError: cannot pickle SignalHub
          → Rust raises: RuntimeError("Transaction isolation failure: …")
            → guards.py:290 catches RuntimeError
              → warnings.warn(..., RuntimeWarning)  # emits visible warning in CI
              → raise                               # re-raises
                → test catches via `except Exception: pass`  # silently swallowed
```

The test intends to verify that accessing `signal.ping` as a process input is architecturally blocked. Instead, it receives a failure for the wrong reason (deepcopy crash) and silently treats it as proof that "the architectural claim is TRUE."

## Impact

- **CI:** Produces 1 `RuntimeWarning` on every run, creating noise that could mask real new warnings.
- **Test Semantics:** `test_claim_zone_enforcement_edge` is passing for the wrong reason — the contract enforcement chain is not tested, only the COW crash path.
- **Developer Trust:** Any engineer who reads the test comment ("If it fails, the claim is TRUE") will form a false mental model of what is actually being enforced.
- **Severity: Medium** — No data corruption, no test failure, but creates misleading CI output and an untested architectural claim.

## Root Cause

### Micro (Logic/Code)

**False assumption:** "The `signal` path in the state graph only contains data values that are safely deepcopy-able."

**Reality:** The `signal` slot contains a `SignalHub` — a Rust-backed system object with no Python pickle support. The COW path has a bypass for `Heavy` zone objects (detected by zone prefix `heavy_*`) but has no bypass for the `signal` zone.

The specific engine code responsible (`engine.rs` lines 768–776):

```rust
let copy_mod = py.import("copy")?;
let shadow = match copy_mod.call_method1("deepcopy", (&val,)) {
    Ok(s) => s.unbind(),
    Err(e) => {
        return Err(pyo3::exceptions::PyRuntimeError::new_err(
            format!("Transaction isolation failure: cannot deepcopy object of type '{type_name}' …")
        ));
    }
};
```

The Heavy Zone bypass checks the path prefix **before** the deepcopy call (lines 757–763). There is no equivalent bypass for the `sig_*` zone.

### Macro (Architecture/System)

The state graph has no formal type-level partition between:
- **User data** (domain, global) — copyable, transactional, owned by business logic
- **System infrastructure objects** (Transaction, SignalHub) — non-copyable, managed by the Rust runtime, never user-writable

The COW engine applies `deepcopy` uniformly to everything it encounters, relying on zone prefix detection (`heavy_*`) as the only escape hatch. SignalHub lives at the `signal` path but the signal zone prefix (`sig_*`) is only checked at the **field level** (e.g., `domain.sig_event`), not at the **top-level** `signal` slot which holds the Hub object itself.

This is the same structural gap that caused INC-020 (Transaction leaked into data graph). The fix in INC-020 removed Transaction from the proxy object graph. The same structural separation has not been applied to SignalHub.

## Why This Was Hard to Detect

1. **Test swallows the exception.** `test_claim_zone_enforcement_edge` uses `except Exception: pass`. Any error counts as "claim enforced."
2. **Warning, not an error.** `guards.py` converts the RuntimeError to a RuntimeWarning before re-raising. pytest counts it as a warning, not a failure.
3. **Zone bypass is path-prefix based.** The engine correctly bypasses Heavy Zone (detected by `heavy_*` field prefix), but `signal` is a top-level slot, not a prefixed field — so the detection logic never fires for it.
4. **Precedent confusion.** INC-020 was fixed at the proxy level for Transaction. The fix is not generalizable to all system objects: a different mechanism is needed for SignalHub.

---

## 8. Comprehensive Analysis & Resolution Plan

### 8.1 Critical Dissection (Integrative Critical Analysis)

> **CORE INSIGHT:** The COW mechanism is designed to copy **data**; `SignalHub` is **infrastructure** — putting them in the same traversal path makes the crash inevitable.

**The Trap (False Assumption):**
The engine's COW deepcopy path assumes the `signal` key in the state graph holds user-readable data values. The test author assumed that ANY exception from the execution confirms architectural enforcement. Both assumptions are wrong in the same chain.

**The Truth:**
- `signal` maps to a `SignalHub` singleton, not to a plain dict of signal values.
- The exception the test receives is a COW isolation failure, not a contract enforcement error.
- The architectural claim ("signal inputs forbidden for stateful processes") is currently **untested** — the test cannot distinguish a `ContractViolationError` from a `RuntimeError`.

**Breaking Point:**
If a developer adds legitimate read access to `ctx.signal` in a proper signal-receiver process, they will hit the same crash — not because of a contract violation, but because `SignalHub` is un-deepcopy-able. This will silently "pass" in any test that uses a bare `except Exception`.

**Hidden Connection:**
INC-020 fixed `Transaction` leaking into the proxy graph. INC-022 shows that `SignalHub` has the same problem at the top-level state graph. The two fixes share a structural root: there is no type-safe boundary enforced by the engine between "system objects" and "user data objects."

### 8.2 Systemic Context (Systems Thinking)

> 🌐 **SYSTEMS ANALYSIS**
> * **Scope:** `engine.rs` COW path → `guards.py` `__getattr__` → `test_chapter_05_compliance.py` test assertion
> * **Dynamics:** Reinforcing loop — test passes → no pressure to fix → warning accumulates → more engineers confused → more tests use bare `except Exception`
> * **Root Structure:** State graph lacks a formal type partition between "user data" (copyable, transactional) and "system objects" (non-copyable, runtime-managed). COW bypass only handles zone-prefix detection, not object type detection.
> * **Leverage Point:** Add a `sig` / `signal` zone bypass in the COW path (same pattern as Heavy Zone), OR implement `__deepcopy__` on `SignalHub` to return a safe sentinel. Fix the test to assert the **specific exception type**.

**Reinforcing Loop (Bad):**
```
Exception swallowed → Test "passes" → Warning ignored → No ticket filed
  → Next run: same warning → grows unnoticed
```

**Balancing Opportunity:**
The same zone-detection logic that skips Heavy zone objects (`resolve_zone(path) == ContextZone::Heavy`) can be extended to skip the `signal` top-level slot — turning the reinforcing failure loop into a stable bypass.

### 8.3 Virtue Audit (Intellectual Virtues)

- **Humility (A):** The analysis is based on reading `guards.py`, `engine.rs`, and the test source. I have not run the test in isolation to confirm the exact stack trace order. The conclusion that "the test passes for the wrong reason" is high-confidence but should be verified by adding an explicit `pytest.raises(RuntimeError)` or `pytest.warns(RuntimeWarning)` assertion.
- **Courage (B):** The test comment says "If it fails, the claim is TRUE." This is wrong and should be said plainly — the test is not validating the architectural claim it was written for.
- **Integrity (D):** The same pattern was identified in INC-020 and resolved. It is intellectually consistent to apply the same root-cause classification here, even though the fix path differs.

### 8.4 Solution Synthesis

#### Immediate Fix (Band-aid)
Make the test honest about what it's actually observing:

```python
@pytest.mark.asyncio
async def test_claim_zone_enforcement_edge(engine):
    engine.register(task_signal_input_allowed_relaxed)
    # The process fails because SignalHub cannot be deepcopied by COW.
    # This is a COW isolation failure, NOT a contract enforcement error.
    # Track under INC-022 — fix the COW path; update this assertion when resolved.
    import pytest
    with pytest.warns(RuntimeWarning, match="Transaction isolation failure"):
        with pytest.raises(RuntimeError):
            await engine.execute("task_signal_input_allowed_relaxed")
```

This eliminates the ambiguous `except Exception: pass`, makes the CI warning explicit, and leaves a clear TODO for the structural fix.

#### Structural Fix (Cure)
In `engine.rs`, extend the zone-bypass logic to also skip deepcopy for the `signal` top-level slot — just as it does for `heavy_*`:

```rust
// engine.rs (around line 757)
if let Some(ref p) = path {
    let zone = crate::zones::resolve_zone(p);
    if zone == crate::zones::ContextZone::Heavy {
        cache.insert(id, (val.clone_ref(py), val.clone_ref(py)));
        return Ok(val);
    }
    // [INC-022 FIX] Signal zone also contains non-copyable runtime objects (SignalHub).
    // Signals are ephemeral and never rolled back; bypass COW.
    if zone == crate::zones::ContextZone::Signal || p == "signal" {
        cache.insert(id, (val.clone_ref(py), val.clone_ref(py)));
        return Ok(val);
    }
}
```

**2nd-order effect check:** Skipping COW for signal reads means a process can see live signal state instead of a snapshot. This is already the intended semantic for signals (ephemeral, not rolled back on failure). The fix aligns implementation with the documented zone semantic.

#### Process Fix (Vaccine)
- Add a `pytest.warns(RuntimeWarning)` / `pytest.raises(RuntimeError)` assertion pattern to the project's test style guide.
- Add a CI lint rule: flag any `except Exception: pass` block in the `tests/` directory (bare suppression pattern).

## Preventive Actions

- [x] Apply immediate fix to `test_claim_zone_enforcement_edge` — replaced `except Exception: pass` with `pytest.raises((PermissionError, RuntimeError))` (v3.0.25)
- [x] Apply zone classification fix in `src/zones.rs`: added `"signal"` and `"cmd"` as full-name Signal zone identifiers alongside `sig_*`/`cmd_*` prefixes (v3.0.25)
- [x] Apply structural fix in `src/guards.rs`: added Signal/Meta/Log zone bypass in `apply_guard()` BEFORE the CoW dict/list path — system infrastructure objects are returned as-is (v3.0.25)
- [x] Verified 382 tests passing, 0 RuntimeWarnings (`pytest tests/ -W error::RuntimeWarning`)
- [ ] Grep for other bare `except Exception: pass` blocks in `tests/` that may hide similar crashes
- [ ] See INC-023 for the follow-on architectural gap exposed by this fix

## Related

- INC-020: Transaction Object Leaks into Data Graph (`Documents/Incidents/by-area/core/INC-020_TransactionLeakCOW.md`)
- `src/engine.rs` lines 757–800 (COW shadow creation + zone bypass)
- `theus/guards.py` lines 288–298 (RuntimeError → RuntimeWarning conversion)
- `tests/02_safety/test_chapter_05_compliance.py` lines 91–115

## Lessons Learned

1. **`except Exception: pass` in tests is an anti-pattern.** It makes tests pass for the wrong reason and hides new incidents.
2. **System objects and user data must not share the same traversal graph.** Any Rust-backed singleton (Transaction, SignalHub, future objects) that is not user data must be explicitly excluded from COW deepcopy paths.
3. **Zone-bypass logic must be consistent.** If the Heavy zone is skipped in COW, the Signal zone must also be skipped for the same structural reason — both hold non-copyable runtime objects.
