---
id: INC-030
title: Commit CoW Full-State Clone — O(N²) Sequential Write Latency
area: core
severity: medium
introduced_in: v3.0 (PyO3 Transaction architecture)
fixed_in: ~
status: open
---

# INC-030: Commit CoW Full-State Clone — O(N²) Sequential Write Latency

## Summary

Every call to `Transaction.__exit__` (the commit path) constructs a **full clone** of the current
engine state via `State::update()`. As the durable document set grows to size N, each successive
commit clones N entries. Across a burst of N sequential writes, total clone work is
`1 + 2 + ... + N = O(N²)`, producing a measurable quadratic latency profile.

This is not a regression introduced by any recent fix. Measurements taken at the v3.0.26 baseline
(pre-v3.0.27 OCC hardening) confirm the same profile. The bottleneck is structural and has been
present since the CoW state model was adopted in v3.0.

---

## Background

### Measurement Methodology

All timing claims below were produced with a **single isolated process, no background tasks**, as
the median of ≥3 runs. Numbers collected concurrently with other terminal activity are excluded
(they introduced approximately 2.5× artificial inflation in earlier preliminary measurements).

### How `State::update()` Currently Works

```rust
// Conceptual pseudocode — src/engine.rs (commit path)
// State::update() — called inside Transaction::__exit__
fn update(current_state: &State, pending_delta: &Delta) -> State {
    let mut new_docs = current_state.documents.clone();  // full clone of N entries
    for (k, v) in &pending_delta.changes {
        new_docs.insert(k, v);
    }
    State { documents: new_docs, version: current_state.version + 1, ... }
}
```

Each commit clones `documents` in full, regardless of how many keys the transaction actually
modified. For a delta of size 1, a clone of N entries is still performed.

---

## Measurements

### Burst Sequential Writes — N × Single-Key Updates

| N    | Elapsed (median) | Scaling ratio vs prior |
|------|-----------------|------------------------|
| 100  | ~0.04s          | —                      |
| 500  | ~0.90s          | ~22×                   |
| 1000 | ~7.5s           | ~8×                    |
| 2000 | ~30s (est.)     | ~4×                    |

The ratio between N=500 and N=1000 (~8×) is consistent with O(N²): doubling N yields 4× the
clone work, but additional allocation overhead (memory pressure, cache misses) pushes the constant
higher at large N.

**Confirmed measurement (v3.0.27, single isolated process):**
- 1000-write burst: 7.40s, 7.77s (two isolated runs)
- Full pytest suite (490 tests): 41.21s / 41.86s / 43.27s (median ~42s)

### Baseline Comparison

| Condition             | Elapsed |
|-----------------------|---------|
| v3.0.26 (pre-patch)   | ~45.6s  |
| v3.0.27 (post-patch)  | ~42.4s  |
| Delta                 | ~−3s    |

The post-patch speedup (~3s) is from OCC path consolidation, not from any CoW optimization. The
root quadratic behavior is unchanged.

---

## False Lead: `_sync_registry_from_core()`

An earlier hypothesis attributed the O(N²) latency to `_sync_registry_from_core()`, the lazy
context synchronization call on the Python side. This hypothesis was experimentally **refuted**:

**Experiment:** Disable `_sync_registry_from_core()` by patching it to a no-op and re-running
a 1000-write burst.

| Condition          | N=1000 Elapsed |
|--------------------|---------------|
| With sync enabled  | 6.32s          |
| With sync disabled | 6.44s          |

The difference is within measurement noise (< 2%). The Python sync layer is **not** a meaningful
contributor to the quadratic growth. The bottleneck is entirely inside the Rust commit path.

---

## Root Cause

### Micro (Code Level)

`State::update()` performs `current_state.documents.clone()` on every commit, regardless of delta
size. The `documents` collection is the primary durable data store and grows monotonically across
the engine's lifetime (keys are rarely deleted). The clone cost scales linearly with collection
size, making the amortized cost of N sequential writes O(N²).

### Macro (Architecture Level)

The CoW model (`State::update()` returns a new `State` object each commit) was adopted for
**snapshot-read correctness**: active transactions always read from an immutable snapshot of the
state at their start time. This is correct and must be preserved.

The structural mistake is that **snapshot-read isolation does not require cloning the entire
state**. It only requires that:
1. Readers hold a reference to the old state for the lifetime of their transaction.
2. Writers produce a new state that does not alias the old one for the keys they modify.

This is precisely what a **delta-based (structural-sharing) approach** achieves: a new state
stores only the changed keys plus an immutable reference (or Arc pointer) to the unchanged
portions of the prior state. Reads of unchanged keys resolve through the reference chain without
copying.

---

## Impact

| Scenario                                             | Impact Level |
|------------------------------------------------------|-------------|
| Long-running accumulation (pipeline, event sourcing) | **High** — latency compounds as document set grows |
| Initial-state population (seed 1000 entries)          | **High** — user-visible startup latency |
| Short-lived burst (< ~100 writes, small documents)   | Low — within noise floor |
| Read-heavy workloads                                  | None |

---

## Proposed Fix Direction

### Option A: Persistent (Structural-Sharing) Map — Recommended

Replace `documents: HashMap<String, Value>` on `State` with a persistent (immutable, structurally
shared) map. Candidates:

- **`im::HashMap` / `im::OrdMap`** from the [`im` crate](https://docs.rs/im) — persistent HAMTs
  with O(1) clone and O(log N) insert, sharing unchanged subtrees between versions.
- **Custom Arc-wrapped segment map** — partition `documents` into immutable Arc'd segments;
  commits copy only the segments containing modified keys.

Under Option A, `State::update()` becomes O(delta_size × log N) instead of O(N), reducing the
burst cost from O(N²) to O(N log N).

```rust
// Pseudocode (im::HashMap approach)
use im::HashMap as PMap;

struct State {
    documents: PMap<String, Value>,  // persistent, Arc-shared subtrees
    version: u64,
    // ...
}

fn update(current: &State, delta: &Delta) -> State {
    let mut new_docs = current.documents.clone();  // O(1) — shares structure
    for (k, v) in &delta.changes {
        new_docs = new_docs.update(k.clone(), v.clone());  // O(log N) per key
    }
    State { documents: new_docs, version: current.version + 1, ... }
}
```

**Expected performance:** 1000-write burst from ~7.5s → < 0.5s (estimated, subject to validation).

### Option B: Epoch-Based Compaction (Simpler, Partial Fix)

Keep the current `HashMap` but add a GC step: when no active transactions reference a prior
state, the engine may discard intermediate snapshots. This reduces peak memory usage but does not
change the per-commit clone cost. **Does not fix the O(N²) scaling.**

### Option C: Write-Ahead Delta Log (Future Architecture)

Store only deltas in the commit path; materialize full state lazily or on explicit checkpoint.
This is the architecture used by MVCC databases. Highest throughput potential, but requires a
significant refactor of state access patterns across the Rust and Python layers.

**Recommendation:** Implement Option A. The `im` crate is mature, maintained, and designed for
exactly this use case. It preserves the CoW semantics (new state is a distinct object that does
not alias the old one) while making clones O(1) and inserts O(log N).

---

## Acceptance Criteria

A fix for INC-030 must satisfy:

1. **Correctness (unchanged):** All existing pytest tests pass without modification.
2. **Snapshot isolation preserved:** A transaction starting at version N must still see a
   consistent snapshot of state at version N, regardless of concurrent commits.
3. **Performance benchmark (new):** `tests/perf/burst_write_benchmark.py` (to be created)
   records median elapsed for N=100, 500, 1000. The N=1000 case must complete in < 1.0s on
   the reference machine (vs ~7.5s current).
4. **No regression in full suite:** `python scripts/Local_CI.py verify` exit 0.

---

## Causal Lineage — Relationship to v3.0.27

INC-030 is **independent of INC-027, INC-028, and INC-029**. Those incidents addressed OCC
bypass vulnerabilities (correctness gaps). INC-030 is a latency/scalability issue. They share
the same transaction commit path (`Transaction::__exit__`) but address orthogonal concerns:

```
Transaction::__exit__  ──┬── OCC correctness  (INC-027, INC-028, INC-029 — RESOLVED in v3.0.27)
                          └── Clone latency    (INC-030 — OPEN, not addressed by v3.0.27)
```

v3.0.27 did **not** worsen or improve the O(N²) scaling. The ~3s improvement observed post-patch
is attributable to OCC path consolidation, not CoW optimization.

---

## What Is NOT the Root Cause

| Hypothesis                           | Verdict           | Evidence                                              |
|--------------------------------------|-------------------|-------------------------------------------------------|
| `_sync_registry_from_core()` latency | **Refuted**       | No-op patch: N=1000 timing unchanged (Δ < 2%)        |
| OCC bypass fixes in v3.0.27          | **Unrelated**     | Baseline at v3.0.26 shows identical quadratic profile |
| Python-side context overhead          | **Refuted**       | Sync no-op experiment eliminates Python layer         |
| GIL contention                        | **Not applicable**| Single-threaded sequential writes; GIL not a factor  |

---

## Prevention & Forward Work

Once INC-030 is resolved:

1. **Benchmark gate:** Add `tests/perf/burst_write_benchmark.py` to `Local_CI.py full`; fail CI
   if N=1000 burst exceeds a configured threshold (e.g., 2.0s).
2. **Architecture note in AGENTS.md:** Add under "Conventions That Matter" that `State::update()`
   must remain O(delta_size × log N), not O(N).
3. **INC-030 resolved marker:** Update `fixed_in` field and add a post-mortem section confirming
   which benchmark result validated the fix.

---

## Related

- INC-020 (`TransactionLeakCOW`): Related CoW semantics — transactions must not share mutable
  state across isolation boundary
- INC-027, INC-028, INC-029: Sibling incidents in `Transaction::__exit__` commit path (OCC
  correctness, now resolved in v3.0.27)
- `src/engine.rs`: Primary implementation site for `State::update()`
- `tests/manual/run_suite.py`: Suite that surfaces the quadratic scaling under sequential load

---

## Lessons Learned

1. **CoW correctness ≠ CoW efficiency.** Snapshot isolation requires that old readers see old
   state; it does not require copying unchanged data. Conflating these requirements leads to
   unnecessary O(N) clones per commit.

2. **Profile before attributing.** The Python sync layer was a plausible suspect, but the
   experiment showed < 2% impact. Without measurement, a fix targeting `_sync_registry_from_core`
   would have been expensive (Python-layer refactor) and ineffective.

3. **Baselines must be isolated.** Measurements taken under background load (other terminals,
   concurrent compilers) can show 2–3× inflation. Use median of ≥3 isolated runs as the
   measurement standard.

4. **O(N²) in a commit path is invisible at small N.** 100 writes takes 0.04s — within acceptable
   latency. At 1000 writes, 7.5s is jarring. At 10,000 writes (a plausible event-sourcing scenario)
   the estimate exceeds 10 minutes. The failure mode is discontinuous and hard to anticipate without
   explicit scaling tests.
