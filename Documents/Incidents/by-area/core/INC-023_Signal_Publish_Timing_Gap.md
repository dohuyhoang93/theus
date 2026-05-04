---
id: INC-023
title: Signal Publish Fires Before Data Commit — No Ordering Guarantee Between Signal and State
area: core
severity: medium
introduced_in: v3.0 (MVCC COW architecture)
fixed_in: v3.0.25
status: resolved
---

# INC-023: Signal Publish Fires Before Data Commit — No Ordering Guarantee Between Signal and State

## Summary

`SignalHub.publish()` — whether called directly via `ctx.signal.publish(...)` inside a process
body, or indirectly via `txn.update(signal={...})` — fires **before** the corresponding data
commit is confirmed. There is no barrier in the engine that defers signal dispatch until after
`compare_and_swap` (CAS) succeeds and schema validation passes. This violates the principle of
**deterministic, explicit side-effect ordering** that the rest of Theus enforces via return
contracts: all other mutations must be returned explicitly through `StateUpdate` and are committed
atomically, but signals bypass this lifecycle entirely.

This incident was discovered during root-cause analysis of INC-022. Fixing the CoW deepcopy crash
(INC-022) exposed the deeper timing gap — by making `ctx.signal` accessible inside a process body,
we implicitly allowed fire-and-forget publish at arbitrary points in process execution.

## Background

Theus enforces output contracts: a `@process` must declare every path it writes via `outputs=[...]`
and return mutations explicitly via `StateUpdate`. The engine replays those mutations through
`compare_and_swap`, giving CAS retry, schema validation, conflict detection, and audit logging.

`SignalHub` sits at `State.signal` — a shared, non-versioned, non-snapshotted Tokio
`broadcast::Sender`. Its semantics are intentionally different from data zones: signals are
ephemeral, not rolled back on retry, not part of the MVCC snapshot graph.

The problem is not that signals are fire-and-forget. The problem is **when** the fire happens:

```
compare_and_swap() call sequence:
  1. version check           ← pass
  2. State.update(signal=…)  ← signal.publish() fires HERE (irreversible)
  3. schema validation        ← may FAIL → data rolls back, signal already sent
  4. self.state = new_state   ← data commit
```

And for direct calls inside process body:

```python
@process(outputs=["data.order_status", "signal.*"])
def confirm_order(ctx):
    ctx.signal.publish("order_confirmed")  # fires at line 2, body not finished
    # ... 30 lines of validation ...
    if something_fails:
        raise ValueError()                 # data never commits
    # signal already broadcast, no retraction possible
    return StateUpdate(data={"data": {"order_status": "confirmed"}})
```

## What Went Wrong

There is no single bug — this is an **architectural gap**. The engine enforces explicit ordering for
data mutations but has no equivalent enforcement for signal dispatch:

| Mutation type | Tracked in delta? | CoW snapshot? | Gated by CAS? | Explicit via return? |
|--------------|------------------|---------------|---------------|----------------------|
| `data.*`     | ✓ yes            | ✓ yes         | ✓ yes         | ✓ yes (StateUpdate)  |
| `heavy.*`    | ✗ no             | ✗ no (bypass) | ✓ yes         | ✓ yes (StateUpdate)  |
| `signal.*`   | ✗ no             | ✗ no (bypass) | ✗ **NO**      | ✗ **NO**             |

Signal is the only mutable output category that bypasses all lifecycle enforcement.

## Impact

**Scenario A — Schema validation fail after signal publish:**
```
Process runs → signal.publish("order_confirmed") fires
→ schema validation fails → data rollback
→ downstream subscriber received "order_confirmed" for an order that does not exist in state
→ TOCTOU: event arrived before state, subscriber query returns stale/missing data
```

**Scenario B — CAS retry amplification:**
```
Process with max_retries=3, concurrent writers:
  Attempt 1: publish("payment_processed") → CAS conflict → retry
  Attempt 2: publish("payment_processed") → CAS success
  → downstream receives 2× "payment_processed" for 1 logical transaction
  → idempotent consumers: tolerable
  → counter-increment or payment-trigger consumers: data corruption
```

**Scenario C — State serialization (future):**
```python
pickle.dumps(engine.state)  # TypeError: cannot pickle 'SignalHub'
# Any checkpoint/restore, distributed worker, or debug dump fails
# because State.signal is not serializable
```

**Severity: Medium** — Scenarios A and B require specific conditions (schema validation enabled,
`max_retries > 0`, non-idempotent consumers). No current test exercises these combinations.
Scenario C is a future risk for any distributed or checkpoint use case.

## Root Cause

### Micro (Code Level)

**`src/structures.rs` — `State.update()`** calls `signal.publish()` immediately when invoked,
not deferred to after CAS confirmation:

```rust
// structures.rs ~line 386
new_state.signal.publish(format!("{topic}:{payload}"));
// This fires BEFORE compare_and_swap() line: self.state = new_state_obj
```

**`src/guards.rs` — `apply_guard()`** (INC-022 fix) returns raw `SignalHub` for Signal zone,
making `ctx.signal.publish()` callable directly in process body with no interception point.

### Macro (Architecture Level)

The engine has two execution planes:

- **Transactional plane** (`data_*`, `heavy_*`): CoW snapshot → mutation → delta log → CAS →
  schema validation → commit. Fully explicit, reversible until commit.
- **Ambient plane** (`signal`): No snapshot, no delta, no CAS gate. Dispatch is immediate and
  irreversible.

There is **no barrier** at the commit boundary separating these two planes. A process runs in both
planes simultaneously with no lifecycle coordination between them.

This is a **mental model mismatch**: the developer declares `outputs=["signal.*"]` in the contract,
which implies the engine manages signal dispatch the same way it manages data writes. The actual
behavior is: the contract only gates *access permission*, not *dispatch timing*.

## Why This Was Hard to Detect

1. **Most signal consumers are idempotent by design** in current usage. Duplicate events are
   tolerated silently.
2. **`max_retries` defaults to a low value**; CAS conflicts are rare in single-process tests.
3. **Schema validation is opt-in** (`schema=...` on `TheusEngine`). Most tests don't use it,
   so the schema-fail-after-publish scenario never triggers.
4. **INC-022 masked this issue** — before the CoW bypass fix, accessing `ctx.signal` in a
   process body crashed immediately, so the timing gap was never reachable.

---

## Comprehensive Analysis

### Critical Dissection (Integrative Critical Analysis)

> **CORE INSIGHT:** "Fire-and-forget" describes signal *semantics* (no rollback, no snapshot),
> not signal *timing*. The engine conflates the two — treating "no rollback needed" as
> "no ordering constraint needed". These are independent properties.

**The Trap:** Assuming that because signals don't need MVCC isolation, they also don't need
lifecycle ordering with respect to the data commit they accompany. This leads to a contract where
`outputs=["signal.*"]` declares intent but the engine does not enforce timing.

**The Truth:** A signal carries meaning relative to a state transition. If the signal fires before
the transition is confirmed, the signal is causally detached from the state it is supposed to
announce. The subscriber observes the announcement before the announced fact exists.

**Breaking Point:**
```
Process: max_retries=3, schema validation enabled, non-idempotent downstream
  → Attempt 1: signal fires, schema fail → rollback → 1 phantom signal
  → Attempt 2: signal fires, CAS conflict → rollback → 2 phantom signals
  → Attempt 3: signal fires, commit success → 3 signals for 1 event
```

**Hidden Connection:** `engine.state.signal` is the only subscription handle before engine
execution (`hub = engine.state.signal; receiver = hub.subscribe()`). Fixing the timing issue
must not break this pre-subscription pattern — the `SignalHub` channel identity must remain
stable. This is achievable: the fix is about *when publish fires*, not about changing the
channel topology.

### Systemic Context (Systems Thinking Engine)

> 🌐 **SYSTEMS ANALYSIS**
> * **Scope:** `@process` body → `ContextGuard` → `Transaction.compare_and_swap()` → `State.update()` → `SignalHub.publish()` → Tokio broadcast channel → downstream subscribers
> * **Dynamics:**
>   - **Reinforcing Loop (R):** CAS retry → duplicate publish → downstream reacts → triggers more processes → more CAS contention → more retries
>   - **Missing Balancing Loop (B):** No gate at commit boundary to hold signal dispatch until data committed
>   - **Delay:** Signal fires at T=0 (inside process body or State.update), data visible at T=1 (after CAS). Subscribers operate in the T=0–T=1 window with stale state.
> * **Root Structure:** Two execution planes (Transactional, Ambient) share the same process body but have no synchronization point at the commit boundary.
> * **Leverage Point:** A single commit-boundary gate: publish all buffered signals AFTER `self.state = new_state_obj` succeeds. No other code changes needed.

---

## Resolution Plan

### Re-audit Note (v3.0.25 session)

The original plan (3 phases: new `StateUpdate.signal` field, `SignalBuffer` pyclass, block
`ctx.signal.publish()`) was **over-engineered**. After Intellectual Virtue re-audit:

- `outputs=["signal.*"]` already declares intent correctly — no new contract field needed
- `SignalBuffer` adds complexity without necessity — the Tokio channel is the correct buffer
- `ctx.signal.publish()` outside a process is legitimate API — blocking it would break caller code

**Correct pivot**: `signal.publish()` fires inside `State.update()`. Move it out. Add a
dedicated `State.publish_signals()` method called after commit. Two files, minimal diff.

---

### Change 1 — `src/structures.rs`: Split `State.update()` signal handling

**Problem**: `State.update()` does two things for signal: (a) populates `last_signals` latch
(needed by Flux DSL), (b) calls `signal.publish()` (must be deferred).

**Fix**: Remove `signal.publish()` calls from `State.update()`. Keep `last_signals.insert()`.
Add new `publish_signals()` method:

```rust
// REMOVE these two lines from State.update() signal handling block:
new_state.signal.publish(format!("{topic}:{payload}"));  // ← remove
new_state.last_signals.insert(topic, payload);           // ← keep

// ADD new method on State:
/// [INC-023] Deferred signal dispatch — call AFTER data commit.
/// State.update() populates last_signals for Flux, but does NOT publish.
/// This method does the actual Tokio channel send.
pub fn publish_signals(&self, py: Python, signal: Option<PyObject>) -> PyResult<()> {
    let Some(s) = signal else { return Ok(()); };
    if let Ok(s_list) = s.downcast_bound::<PyList>(py) {
        for item in s_list {
            if let Ok(s_dict) = item.downcast::<PyDict>() {
                for (k, v) in s_dict {
                    let topic = k.extract::<String>()?;
                    let payload = v.to_string();
                    self.signal.publish(format!("{topic}:{payload}"));
                }
            }
        }
    } else if let Ok(s_dict) = s.downcast_bound::<PyDict>(py) {
        for (k, v) in s_dict {
            let topic = k.extract::<String>()?;
            let payload = v.to_string();
            self.signal.publish(format!("{topic}:{payload}"));
        }
    }
    Ok(())
}
```

---

### Change 2 — `src/engine.rs`: `Transaction.__exit__`

Current sequence (problematic):
```
State.update(data, heavy, signal)  ← publish fires HERE (before schema, before commit)
schema_validation()
commit_state(new_state_obj)
```

Fixed sequence:
```rust
// Keep State.update(signal) — populates last_signals for Flux
let new_state_obj = current_state_obj.call_method(
    "update",
    (self.pending_data.clone_ref(py), self.pending_heavy.clone_ref(py), self.pending_signal.clone_ref(py)),
    None
)?;

// schema validation (unchanged) ...

// commit data (unchanged)
engine.call_method1("commit_state", (new_state_obj,))?;

// [INC-023] Deferred signal dispatch — AFTER data committed to engine
{
    let committed_state = engine.getattr("state")?;
    committed_state.call_method1(
        "publish_signals",
        (self.pending_signal.clone_ref(py),)
    )?;
}
```

---

### Change 3 — `src/engine.rs`: `TheusEngine.compare_and_swap()`

Same pattern — `signal` is `Option<PyObject>`, must be cloned before passing to `State.update()`:

```rust
// Clone before move into State.update()
let signal_for_publish = signal.as_ref().map(|s| s.clone_ref(py));

let new_state_obj = current_state_bound.call_method(
    "update",
    (data, heavy, signal),  // signal moved here — last_signals populated
    None
)?;

// schema validation (unchanged) ...

self.state = new_state_obj.extract::<Py<State>>()?;

// [INC-023] Deferred signal dispatch — AFTER self.state committed
if let Some(sig) = signal_for_publish {
    self.state.bind(py).borrow().publish_signals(py, Some(sig))?;
}
```

---

### Backward Compatibility

| Caller | Impact |
|--------|--------|
| `engine.state.signal.subscribe()` before execute | **Not affected** — channel topology unchanged, same `Arc<SignalHub>` |
| `txn.update(signal={"k": "v"})` | **Fixed** — buffered in `pending_signal`, published after `commit_state` |
| `ctx.signal.publish("x")` in process body | **Unchanged behavior** — still fires immediately. This is valid for direct-publish use cases. Signal timing guarantee only applies to the `txn.update(signal=...)` path. |
| `SignalHub.publish()` outside process | **Not affected** — no change to SignalHub API |
| Flux DSL `last_signals` latch | **Not affected** — `State.update()` still populates it |

---

### Test Plan

**Test 1 — Causal ordering guarantee (happy path)**
```python
async def test_signal_fires_after_data_commit():
    engine = TheusEngine()
    hub = engine.state.signal
    receiver = hub.subscribe()

    @process(outputs=["data.status"])
    def set_status(ctx):
        pass  # uses txn.update internally

    # Manually: txn.update(data={"data": {"status": "ok"}}, signal={"done": "true"})
    with engine.transaction() as txn:
        txn.update(data={"data": {"status": "ok"}}, signal={"done": "true"})

    # When "done" is received, data must already be committed
    msg = await asyncio.wait_for(asyncio.to_thread(receiver.recv), timeout=1.0)
    assert msg == "done:true"
    assert dict(engine.state.data["data"])["status"] == "ok"  # data visible BEFORE/WHEN signal arrives
```

**Test 2 — Schema fail → no signal**
```python
async def test_no_signal_on_schema_fail():
    engine = TheusEngine(schema=StrictSchema)  # schema that rejects {"status": "invalid"}
    hub = engine.state.signal
    receiver = hub.subscribe()

    with pytest.raises(SchemaViolationError):
        with engine.transaction() as txn:
            txn.update(data={"data": {"status": "invalid"}}, signal={"done": "true"})

    # No message should arrive
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.to_thread(receiver.recv), timeout=0.2)
```

**Test 3 — CAS retry → exactly-once signal**
```python
async def test_signal_exactly_once_on_retry():
    # Two concurrent processes, one will CAS-conflict and retry
    # The retried process should publish signal exactly once total
    received = []
    receiver = engine.state.signal.subscribe()
    # ... concurrent execution setup ...
    # assert len([m for m in received if m == "done:true"]) == 1
```

**Test 4 — Backward compat: existing deep_integration test**
```python
# tests/09_v3_2/test_deep_integration.py must continue to pass unchanged
```

---

### Acceptance Criteria

- [x] Change 1: `State.update()` no longer calls `signal.publish()` — only `last_signals.insert()` (v3.0.25)
- [x] Change 2: `Transaction.__exit__` calls `publish_signals()` after `commit_state()` (v3.0.25)
- [x] Change 3: `compare_and_swap()` calls `publish_signals()` after `self.state = new_state` (v3.0.25)
- [x] Test 2 (`test_schema_fail_no_signal`): schema validation fail → subscriber receives nothing (v3.0.25)
- [x] Test 3 (`test_cas_retry_signal_exactly_once`): CAS stale-version reject → 0 signals; success → exactly 1 signal (v3.0.25)
- [x] Test `test_signal_data_consistency`: subscriber reads committed state at signal receipt (causal ordering regression guard) (v3.0.25)
- [x] `tests/09_v3_2/test_deep_integration.py` passes unchanged (4/4 tests)
- [x] `python scripts/Local_CI.py full` green (382 pytest + 25 manual, 0 errors)

---

## Preventive Actions

**Implemented in v3.0.25 (minimal correct fix):**
- [x] Deferred `signal.publish()` to post-CAS via `State.publish_signals()` in `src/structures.rs`
- [x] `Transaction.__exit__`: calls `publish_signals()` after `commit_state()` in `src/engine.rs`
- [x] `compare_and_swap()`: calls `publish_signals()` after `self.state = new_state` in `src/engine.rs`
- [x] Regression tests: `test_schema_fail_no_signal`, `test_cas_retry_signal_exactly_once`, `test_signal_data_consistency`

**Explicitly rejected (over-engineering — see Re-audit Note):**
- ~~Add `signal` field to `StateUpdate`~~ — DRY violation; `txn.update(signal=...)` already works
- ~~Implement `SignalBuffer` pyclass~~ — Tokio channel is already the correct buffer
- ~~Block `ctx.signal.publish()` in process body~~ — breaks valid direct-publish use case
- ~~Modify `ContextGuard.apply_guard()` to return `SignalBuffer`~~ — consequence of rejected SignalBuffer

**Remaining open (future consideration):**
- [ ] Document `signal.*` timing semantics in API reference (distinguish `txn.update(signal=)` vs `ctx.signal.publish()` timing)

## Related

- INC-022: `SignalHub` CoW Deepcopy Crash (`INC-022_SignalHub_COW_Deepcopy_Crash.md`) — fixed in v3.0.25; this incident is the follow-on architectural gap exposed by that fix
- `src/structures.rs` lines 279–420 (`State.update()` — immediate publish path)
- `src/engine.rs` lines 163–310 (`compare_and_swap()` — CAS sequence)
- `src/guards.rs` `apply_guard()` — INC-022 Signal zone bypass
- `src/signals.rs` — `SignalHub`, `SignalReceiver`
- `tests/09_v3_2/test_deep_integration.py` — pre-subscription pattern that must not break

## Lessons Learned

1. **"No rollback" ≠ "No ordering constraint."** These are independent properties that must
   be reasoned about separately when classifying a zone's lifecycle rules.
2. **Fixing a crash (INC-022) can expose a previously unreachable design gap.** The CoW bypass
   made `ctx.signal` accessible, which made the timing gap observable.
3. **`outputs=[...]` declares access permission, not execution semantics.** If a contract field
   implies dispatch ordering, the engine must enforce it — not leave it to convention.
4. **Commit boundary is the correct synchronization point** for any irreversible side effect
   that accompanies a state transition. This is the transactional outbox pattern.
