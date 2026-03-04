---
id: INC-020
title: Transaction Object Leaks into Data Graph, Crashes COW Deepcopy
area: core
severity: high
introduced_in: v3.0 (MVCC Transaction architecture)
fixed_in: v3.0.23 (Python workaround) / v3.3 (Rust root fix)
status: resolved
---

# INC-020: Transaction Object Leaks into Data Graph, Crashes COW Deepcopy

## Summary

Rust-managed Transaction objects leak into the Python data graph. When ContextGuard performs a COW (Copy-On-Write) deepcopy to enforce transaction isolation, it encounters these non-copyable Transaction objects and raises `RuntimeError: Transaction isolation failure: cannot deepcopy`. This completely blocks the post-experiment report generation pipeline.

## Background

Theus v3.0 uses an MVCC (Multi-Version Concurrency Control) architecture to isolate data between processes. Whenever a process accesses data through ContextGuard, the COW mechanism creates a deep copy of the data subtree to ensure one process cannot affect another.

ContextGuard sits between Python processes and the Rust-backed State. When a process reads `ctx.domain_ctx` or `ctx['domain']`, ContextGuard triggers a deepcopy on the entire data subtree at that node.

## What Went Wrong

The workflow orchestrator executes four processes sequentially: `p_aggregate_results` → `p_plot_results` → `p_analyze_results` → `p_save_summary`. The last three access `ctx.domain_ctx` directly, which triggers the ContextGuard COW deepcopy, which encounters a Transaction object embedded in the dict, which raises a RuntimeError.

Failure chain:
```
ctx.domain_ctx
  → ContextGuard.__getattr__('domain_ctx')
    → COW deepcopy(data_graph['domain_ctx'])
      → Encounters embedded Transaction object
        → RuntimeError: cannot deepcopy
```

## Impact

- **Who:** The entire post-experiment reporting pipeline.
- **What broke:** 110 episodes complete successfully, but no plots, analysis, or summary reports are generated. Raw data remains safe in the metrics file, but the full orchestration must be re-run to produce reports.
- **Severity:** High — each experiment run takes 7–8 minutes, and there is no standalone retry mechanism for the report pipeline alone.

## Root Cause

**Micro cause (Logic):** The implicit assumption that *"COW deepcopy always succeeds because the data graph only contains pure Python types"* is incorrect. In practice, the SupervisorProxy retains references to Transaction objects within the Python data graph as part of the state management machinery.

**Macro cause (System):** There is no enforced boundary between "user data" (safely copyable) and "system objects" (non-copyable) within the data graph. Transaction, which is a transient object with a scoped lifecycle, is stored at the same level as domain data.

## Why This Was Hard to Detect

1. **Only occurs when processes access domain_ctx via ContextGuard** — unit tests typically use plain dicts, bypassing COW entirely.
2. **Only manifests in post-processing** — 110 episodes completing successfully creates a false impression of system stability.
3. **Misleading error message** — `cannot deepcopy object of type 'dict'` suggests a problem with a Python dict, while the actual cause is a Rust-backed Transaction object.
4. **No integration tests for the report pipeline** — no test exercises the aggregate → plot → save chain through ContextGuard.

## Resolution

### Applied Fix (Mitigation)

**Three process files** (`p_plot_results.py`, `p_save_summary.py`, `p_aggregate_results.py`) — replaced direct `ctx.domain_ctx` access with `get_domain_ctx()` and `get_attr()` helpers. These functions bypass ContextGuard by accessing `_inner._target` directly, avoiding COW.

**`context_helpers.py`** — reordered resolution priority: `_inner._target` (no COW) first, `ctx['domain']` (triggers COW) as a last-resort fallback with `warnings.catch_warnings()` suppression.

**`p_plot_results.py`** — added `matplotlib.use('Agg')` before importing pyplot to prevent tkinter GUI-threading crashes when running on asyncio worker threads.

### Rust Core Fix (v3.3 — already applied)

The root cause was already addressed at the Rust level in v3.3:

1. **`proxy.rs` (line 35–38):** `SupervisorProxy` no longer stores `Transaction` as a field. It stores only a boolean `is_mutable` flag. Transaction is queried from Python `contextvars` on demand. This prevents Transaction refs from leaking into the serializable object graph.
2. **`structures.rs` (line 629–630):** `ProcessContext.domain` getter marked `[FIX v3.3]` — Transaction is NOT injected into the SupervisorProxy returned to user code.
3. **`engine.rs` (line 855–868):** `Transaction.__deepcopy__` and `Transaction.__reduce__` both raise explicit `RuntimeError` with clear messages, making any remaining leak immediately visible.

The residual warnings occurred because `ContextGuard` (`guards.rs` line 30) still holds `tx: Option<Py<Transaction>>` for COW shadow creation. The Python-side workaround (`context_helpers.py`) bypasses this path entirely.

## Long-Term Changes

- Transaction is architecturally separated from the user data graph at the Rust level (v3.3).
- `get_domain_ctx()` and `get_attr()` are the mandatory access pattern for orchestrator processes.
- `context_helpers.py` prioritizes COW-free access paths.

## Preventive Actions

- [x] Rust Core: Transaction removed from SupervisorProxy fields (v3.3).
- [x] Rust Core: Transaction.__deepcopy__ raises explicit error.
- [x] 7 integration tests in `test_flux_integration_4case.py` covering process pipelines through TheusEngine.
- [ ] Audit all processes in `src/orchestrator/processes/` for direct `ctx.domain_ctx` access.

## Related

- INC-005: ContextLeak (same Transaction/Context boundary family)
- INC-008: AsyncDeadlock (same execute_workflow pipeline)
- Files modified: `p_plot_results.py`, `p_save_summary.py`, `p_aggregate_results.py`, `context_helpers.py`

## Lessons Learned

1. **A safety mechanism (COW) can become a source of failure** when the data it protects contains objects incompatible with that mechanism.
2. **The boundary between "data" and "infrastructure" must be enforced at the type level** — Transaction is infrastructure and must never appear in the user data layer.
3. **Unit tests with mock data do not catch integration failures** — end-to-end tests that exercise the actual ContextGuard + COW path are essential.
