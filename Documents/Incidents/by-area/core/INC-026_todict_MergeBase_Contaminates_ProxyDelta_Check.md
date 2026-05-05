---
id: INC-026
title: "to_dict() Merge Base Contamination Causes _proxy_delta_exists to Block All Output Mapping"
area: core
severity: high
introduced_in: v3.0.26 (commit 9e19cff, INC-021 fix)
fixed_in: v3.0.26-patch (emotional-agent downstream patch)
status: resolved
created: 2026-05-04
author: "Do Huy Hoang"
---

# INC-026: `to_dict()` Merge Base Contamination Causes `_proxy_delta_exists` to Block All Output Mapping

## Summary

A Python-layer merge base initialization bug introduced in the INC-021 fix commit (`9e19cff`) silently blocked **all** return-value output mapping for processes that declare `outputs=[...]` and whose output namespace (`domain.*`) was not touched via proxy mutation. When `pending_data[key]` did not yet exist, the code initialized it from `BaseDomainContext.to_dict()` — a full domain snapshot — pre-populating every domain field. A downstream guard (`_proxy_delta_exists`) then found each field already present and concluded a proxy mutation had occurred, silently skipping every return value. The fix is a **one-line change**: use an empty dict `{}` instead of `to_dict()` as the merge base. `_proxy_delta_exists` itself is semantically correct and remains in place.

## Background

Theus POP processes can write state in two ways:
1. **Proxy mutation**: `ctx.domain.field = value` inside the process body — tracked by the Rust CoW shadow system.
2. **Explicit return**: `return value` with a matching `outputs=[...]` contract — mapped by the Python `_attempt_execute()` output mapping loop.

Theus POP processes support two write patterns that co-exist:
1. **Proxy mutation**: `ctx.domain.field = value` — tracked by the Rust CoW shadow system, committed via inferred shadow deltas.
2. **Explicit return**: `return value` with `outputs=[...]` — mapped by the Python `_attempt_execute()` output mapping loop.

For hybrid processes that do BOTH (proxy write + return an ack string like `"ok"`), the Python guard `_proxy_delta_exists` correctly preserves the proxy value: if a path was already written by a proxy, the return value is treated as an acknowledgement and skipped. This is the intended behavior for patterns like `ctx.domain.value = v; return "ok"`.

The INC-021 fix commit (`9e19cff`) also introduced a **merge base initialization** change that inadvertently broke this guard by inflating the data it checks.

## What Went Wrong

Two bugs were introduced in the same commit at the Python output mapping layer:

### The Single Bug — `to_dict()` Merge Base Contamination

When the output mapping loop processes a `domain.*` path and `pending_data['domain']` does not yet exist (i.e., the process did NOT touch `ctx.domain` via proxy mutation, so `build_pending_from_deltas()` produced no `'domain'` entry), the code initializes it as a **full domain snapshot**:

```python
# INC-021 commit (9e19cff) — BEFORE fix:
if key not in pending_data:
    curr_wrapper = getattr(self.state, key, None)
    if hasattr(curr_wrapper, "to_dict"):
        pending_data[key] = curr_wrapper.to_dict()  # ← Full snapshot — BUG
```

`BaseDomainContext.to_dict()` returns **all** non-SIGNAL, non-Heavy domain fields. Result: `pending_data['domain']` is pre-populated with `{'experiments': [], 'output_dir': 'results', 'active_experiment_idx': 0, ...}` — even though the process never mutated any of these via proxy.

Downstream, `_proxy_delta_exists` checks whether the dotted path exists in `pending_data`. Because the snapshot pre-populated every field, the check returns `True` for all of them — triggering the proxy-wins skip for fields that were **never proxy-written**.

**Note:** `_proxy_delta_exists` is semantically correct in isolation. Its precondition is that `pending_data` contains only actual proxy writes. The bug violated this precondition by contaminating `pending_data` with a full state snapshot.

**Contrast — when the path IS proxy-written (correct behavior preserved):**
```
Process does: ctx.domain.value = v; return "ok"
  → build_pending_from_deltas() → pending_data["domain"]["value"] = v
  → pending_data["domain"] ALREADY exists (from shadow delta)
  → Fix 1 init (empty dict) is SKIPPED (key already present)
  → _proxy_delta_exists(pending_data, "domain.value") → True  (v is there)
  → return "ok" is skipped — proxy value v wins  ✓
```

**Failing case — return-only process (broken before fix, correct after):**
```
Process does: return experiments_list  (no proxy mutation)
  → build_pending_from_deltas() → pending_data["domain"] does NOT exist
  → BEFORE fix: pending_data["domain"] = to_dict() → {"experiments": [], ...}
  → _proxy_delta_exists(pending_data, "domain.experiments") → True  ([] from snapshot!)
  → return experiments_list is skipped — [] stays  ✗

  → AFTER fix: pending_data["domain"] = {}
  → _proxy_delta_exists(pending_data, "domain.experiments") → False  (empty dict)
  → pending_data["domain"]["experiments"] = experiments_list  ✓
```

## Impact

- **`p_load_config`** returns `{'domain.experiments': [...], ...}` without proxy-mutating `ctx.domain`. `build_pending_from_deltas()` produces no `'domain'` entry. `to_dict()` snapshot init pre-fills `pending_data['domain']['experiments'] = []`. `_proxy_delta_exists` returns True. Return value discarded. Downstream: `sig_max_episodes = 0`, episode loop never starts.
- **`p_advance_episode`** returns `sig_episode_counter = N+1` — `sig_*` fields are excluded from `to_dict()` (SIGNAL zone), so they are NOT blocked by this bug. However, if the same process accesses a non-SIGNAL field via proxy (producing a shadow delta), then re-enters a return-only path for that field, the correct `_proxy_delta_exists` behavior takes over.
- **Severity: High** — Silent data loss with no error, no warning, and no test failure. The engine reports success, metrics log, but experiments produce zero episodes.

## Root Cause

### Micro (Logic/Code)

**Violated precondition of `_proxy_delta_exists`:**

> Precondition: `pending_data` contains only entries from `build_pending_from_deltas()` (actual proxy writes) OR explicitly set by previous output mapping.

The `to_dict()` initialization violated this precondition by injecting the full current state as if it were proxy-written.

`_proxy_delta_exists` itself is logically correct: "if this path was proxy-written, treat the return value as an ack." The bug is in its caller — the merge base init should be `{}` (empty), not `to_dict()` (snapshot).

### Macro (Architecture/System)

**Implicit contract of `pending_data` not enforced:**

| Location | Role |
|---|---|
| `build_pending_from_deltas()` (Rust) | Starts from empty dict, adds ONLY actual proxy writes |
| `pending_data[key] = {}` init (Python, after fix) | Preserves empty-dict contract when proxy made no writes |
| `pending_data[key] = to_dict()` init (Python, BEFORE fix) | **Violated the contract** — snapshot fields masquerade as proxy writes |

The contract "pending_data contains only proxy writes + current output mapping writes" is relied upon by `_proxy_delta_exists` but was never written down or tested.

## Why This Was Hard to Detect

1. **Silent success**: The engine committed, the transaction version incremented, and no exception was raised. The only observable symptom was `domain.experiments = []` after `p_load_config` — which looked like a configuration problem, not an engine problem.
2. **`to_dict()` exclusion of `sig_*` fields**: SIGNAL zone fields (`sig_episode_counter`, etc.) are not included in the snapshot, so `_proxy_delta_exists` returned `False` for them. Processes that only return `sig_*` fields appeared to work correctly, masking the pattern.
3. **Hybrid pattern tests pass**: The pre-existing proxy+ack tests (`test_proxy_mutation_stress_4case.py`) use processes that DO proxy-write before returning. `build_pending_from_deltas()` already puts the proxy value in `pending_data`, so the `to_dict()` init branch is never reached (the key is already present). Those tests pass with both the buggy and fixed code — providing no signal that the merge base init was wrong.
4. **No regression test for return-only output mapping**: There is no test asserting "process that returns non-None without proxy mutation has that value committed." Tests focus on observable behavior (episodes run) rather than the intermediate output-mapping step.

## Resolution

**One fix** applied to `theus/engine.py` in `_attempt_execute()`, POP output mapping section:

### Fix — Empty merge base instead of `to_dict()` snapshot

```python
# BEFORE (INC-021 commit):
if key not in pending_data:
    curr_wrapper = getattr(self.state, key, None)
    if hasattr(curr_wrapper, "to_dict"):
        pending_data[key] = curr_wrapper.to_dict()  # ← Full snapshot — BUG
    elif isinstance(curr_wrapper, dict):
        pending_data[key] = curr_wrapper.copy()
    else:
        pending_data[key] = curr_wrapper

# AFTER (INC-026 fix):
# [FIX v3.0.26-patch] Use empty dict instead of to_dict() snapshot.
# Using to_dict() caused _proxy_delta_exists to treat snapshot fields
# as "already set by proxy mutation", skipping legitimate return-value
# updates (e.g. domain.experiments after load_config).
# Rust CAS performs a key-level MERGE, so empty-dict init is safe.
if key not in pending_data:
    pending_data[key] = {}  # Merge base: Rust CAS will preserve unchanged fields
```

**Why safe:** Rust CAS `compare_and_swap` performs field-level merge (`deep_update_inplace`). An empty `pending_data['domain']` passed to `tx.update()` does not erase unchanged fields — Rust merges only the keys present. Verified empirically: partial `{'domain': {'experiments': [...]}}` update preserves `output_dir` and all other unrelated fields.

**`_proxy_delta_exists` NOT removed:** The guard is semantically correct. After the fix, `pending_data[key]` starts as `{}` when no proxy write occurred, so `_proxy_delta_exists` correctly returns `False` for return-only paths. For processes that DO proxy-write a field, `build_pending_from_deltas()` puts the value there first, `pending_data[key]` is already populated, the `{}` init branch is skipped, and `_proxy_delta_exists` correctly returns `True` — preserving proxy-wins behavior for hybrid proxy+ack patterns.

## Long-Term Changes

- **Invariant established:** `pending_data[key]` in the Python output mapping loop MUST start from an empty dict (not a state snapshot) when the key is not yet present. Rust CAS handles field preservation.
- **Hybrid proxy+return policy preserved:** `_proxy_delta_exists` correctly implements "proxy-wins" for fields that were proxy-written in the same transaction. This is the intended behavior and remains unchanged.
- **Interaction invariant:** The precondition of `_proxy_delta_exists` — "pending_data contains only actual proxy writes" — must be maintained by all callers. `to_dict()` (or any other snapshot mechanism) must never be used as a merge base in the output mapping loop.

## Preventive Actions

- [x] **Add regression test** in `theus/tests/`: process with `outputs=['domain.field']` returns a non-None value → assert that value appears in committed state. Covered by `tests/11_rfc001/test_inc026_output_mapping_bypass.py` (INV-1 through INV-6 + integration, 11 tests total).
- [x] **Add regression test**: `p_load_config` equivalent — process returns list for a domain field that starts empty → list must be present after commit. See `test_INV1_return_value_populates_existing_empty_list`.
- [ ] **Update docstring on `_proxy_delta_exists`**: clarify that its precondition is "pending_data contains ONLY actual proxy writes from build_pending_from_deltas() — NOT inflated by to_dict() or any snapshot." Add explicit note that the `{}` init (Fix 1) is what maintains this precondition.
- [ ] **Document the hybrid proxy+ack pattern** in the theus developer guide: `ctx.domain.field = value; return "ok"` — proxy wins, ack is not applied. Contrast with return-only: `return value` — return value is committed. Return `None` to unconditionally skip output mapping for a slot.

## Related

- **INC-021**: `INC-021_Transaction_Snapshot_Lag.md` — established explicit-wins policy at Rust level; INC-026 was introduced in the same fix commit.
- **Commit**: `9e19cff` ("fix INC-021 add pyright, clippy pedantic to CI/CD") — source of both fixes.
- **Downstream**: `emotional-agent` project — first consumer to trigger this bug via `p_load_config` (non-SIGNAL return value) and `p_advance_episode`.

## Lessons Learned

1. **Guards with preconditions must document and enforce their preconditions.** `_proxy_delta_exists` is correct but fragile: it breaks silently if the dict it inspects is ever pre-populated from a non-proxy source. The fix is one line, but the underlying risk is that the precondition is invisible.
2. **`to_dict()` (and any snapshot) as a merge base is dangerous in delta pipelines.** Pre-populating `pending_data` with a full domain snapshot creates a semantic ambiguity between "current state" and "written state" that is invisible to the caller and corrupts any delta-based guard downstream.
3. **Integration tests through behavior can miss unit-level invariant violations.** The proxy+ack tests passed with the buggy code because they never triggered the `to_dict()` init branch. Only a test that exercises return-only output mapping (no proxy write) would have caught the bug. Unit tests for each output pattern — proxy-only, return-only, hybrid — are necessary.
4. **Silent success is the most dangerous failure mode.** An engine that commits, increments version, and logs success while silently discarding all return values has zero observability signals. Output mapping correctness requires its own invariant tests independent of downstream experiment behavior.
