"""INC-030 Burst Write Benchmark Suite

Measures sequential write scaling across multiple real-world access patterns:
1. SingleKeyBurst: same key updated N times (State size = 1 key)
2. DistinctKeyBurst: N distinct keys inserted (State size grows monotonically to N)
3. NestedDomainBurst: nested dict update (domain.counter)
4. ContextWithProxyBurst: Engine with populated context and domain proxy mutation
"""

import time
import statistics
import sys
from dataclasses import dataclass
from theus import TheusEngine, BaseDomainContext, BaseSystemContext

@dataclass
class BenchDomain(BaseDomainContext):
    counter: int = 0
    items: dict = None

@dataclass
class BenchContext(BaseSystemContext):
    domain: BenchDomain = None

def bench_single_key(n: int) -> float:
    e = TheusEngine()
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"counter": i})
    return time.perf_counter() - t0

def bench_distinct_keys(n: int) -> float:
    e = TheusEngine()
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={f"key_{i}": i})
    return time.perf_counter() - t0

def bench_nested_domain(n: int) -> float:
    e = TheusEngine()
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"domain": {"counter": i}})
    return time.perf_counter() - t0

def bench_context_sync(n: int) -> float:
    ctx = BenchContext(domain=BenchDomain(counter=0, items={}))
    e = TheusEngine(ctx)
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"domain": {"counter": i}})
    return time.perf_counter() - t0

def bench_prepopulated(initial_keys: int, n: int = 1000) -> float:
    e = TheusEngine()
    initial_dict = {f"k_{i}": i for i in range(initial_keys)}
    with e.transaction() as tx:
        tx.update(data=initial_dict)
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"counter": i})
    return time.perf_counter() - t0

def bench_prepopulated_5000(n: int) -> float:
    return bench_prepopulated(5000, n)

def bench_nested_subdict_growth(n: int) -> float:
    """Scenario 6a: Direct transaction update on growing nested sub-dict.
    Measures deep_merge_cow() with single-leaf delta. Stays bounded (~12-13 µs/op)
    because only 1 leaf crosses FFI and Python avoids full-dictionary cloning.
    """
    e = TheusEngine(context={"domain": {"documents": {}}})
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"domain": {"documents": {f"doc_{i}": {"idx": i}}}})
    return time.perf_counter() - t0

def bench_nested_process_growth(n: int) -> float:
    """Scenario 6b: Growing nested sub-dict via @process with full dict return.
    Compound O(N²) bottleneck:
    1. Python copies N items: docs = dict(ctx.domain.documents)
    2. Full N-element dict crosses FFI boundary
    3. Rust deep_merge_cow iterates N items and copies target_dict
    Matches test_case3_bien_burst_no_document_loss (BURST_N=1000 taking ~6.3s-7.5s).
    """
    import asyncio
    from theus.contracts import process

    @process(inputs=["domain.documents"], outputs=["domain.documents"])
    async def p_save_doc(ctx, doc_id, payload):
        docs = dict(ctx.domain.documents)
        docs[doc_id] = payload
        return docs

    async def _run():
        e = TheusEngine(context={"domain": {"documents": {}}})
        e.register(p_save_doc)
        for i in range(n):
            await e.execute(p_save_doc, doc_id=f"DOC-{i:04d}", payload={"idx": i})

    t0 = time.perf_counter()
    asyncio.run(_run())
    return time.perf_counter() - t0

def bench_nested_process_delta(n: int) -> float:
    """Scenario 7: Growing nested sub-dict via @process with delta return.
    Benchmarks the primary pattern remediation lever for INC-030:
    Returning only {doc_id: payload} eliminates Python dict copying and FFI serialization,
    reducing N=1000 from ~6.4s to ~0.046s-0.050s (~130× speedup).
    Includes explicit post-run assertion verifying 100% data preservation.
    """
    import asyncio
    from theus.contracts import process

    @process(inputs=["domain.documents"], outputs=["domain.documents"])
    async def p_save_delta(ctx, doc_id, payload):
        return {doc_id: payload}

    async def _run():
        e = TheusEngine(context={"domain": {"documents": {}}})
        e.register(p_save_delta)
        for i in range(n):
            await e.execute(p_save_delta, doc_id=f"DOC-{i:04d}", payload={"idx": i})
        # Data integrity verification: assert 100% key preservation and payload correctness
        committed_docs = e.state.data.get("domain", {}).get("documents", {})
        if len(committed_docs) != n:
            raise AssertionError(f"Scenario 7 data loss: expected {n} docs, got {len(committed_docs)}")
        for i in range(n):
            key = f"DOC-{i:04d}"
            if key not in committed_docs:
                raise AssertionError(f"Scenario 7 missing key: {key}")
            if committed_docs[key] != {"idx": i}:
                raise AssertionError(f"Scenario 7 corrupted payload for key {key}: expected {{'idx': {i}}}, got {committed_docs[key]}")

    t0 = time.perf_counter()
    asyncio.run(_run())
    return time.perf_counter() - t0

def run_scenario(name: str, fn, n_list=None, reps=3) -> dict[int, float]:
    if n_list is None:
        n_list = (100, 500, 1000)
    print("\n==========================================")
    print(f"Scenario: {name}")
    print("==========================================")
    results = {}
    for n in n_list:
        times = []
        for _ in range(reps):
            times.append(fn(n))
        med = statistics.median(times)
        mean = statistics.mean(times)
        per_op_us = (med / n) * 1e6
        results[n] = med
        print(f"  N={n:4d} | Median: {med:.4f}s | Mean: {mean:.4f}s | Per-op: {per_op_us:6.2f} µs")
    return results

def main():
    print("Starting INC-030 Burst Write Benchmark Suite (Python 3.14 + Theus Core)...")
    print("Methodology: All scenarios evaluated as median of 3 isolated runs.")

    res1 = run_scenario("1. Flat Single Key (O(1) state size)", bench_single_key, reps=3)
    res2 = run_scenario("2. Distinct Keys Growth (State size grows 1..N, im::HashMap)", bench_distinct_keys, reps=3)
    res3 = run_scenario("3. Nested Domain Dict (Compact subdict, deep_merge_cow)", bench_nested_domain, reps=3)
    res4 = run_scenario("4. Context + Proxy Sync (_sync_registry_from_core)", bench_context_sync, reps=3)
    res5 = run_scenario("5. Prepopulated State (5,000 keys durable, O(K) sync)", bench_prepopulated_5000, reps=3)
    res6a = run_scenario("6a. Growing Nested Sub-dict (Direct txn leaf delta)", bench_nested_subdict_growth, reps=3)
    res6b = run_scenario("6b. Process Contract Full Dict Return (INC-030 Bottleneck)", bench_nested_process_growth, reps=3)
    res7 = run_scenario("7. Process Contract Delta Return (Pattern Baseline — Verified)", bench_nested_process_delta, reps=3)

    # -------------------------------------------------------------------------
    # Regression Ceilings: CI Guard Rails against catastrophic regressions
    # Set to current baseline + safety margin to prevent false-positive CI noise.
    # -------------------------------------------------------------------------
    regression_ceilings = [
        ("Scenario 1 (N=1000)", res1[1000], 0.05),     # Normal ~0.006s
        ("Scenario 2 (N=1000)", res2[1000], 0.15),     # Normal ~0.040s
        ("Scenario 3 (N=1000)", res3[1000], 0.05),     # Normal ~0.007s
        ("Scenario 4 (N=1000)", res4[1000], 0.05),     # Normal ~0.009s
        ("Scenario 5 (N=1000)", res5[1000], 1.50),     # Normal ~0.45s (O(K) sync)
        ("Scenario 6a (N=1000)", res6a[1000], 0.08),   # Normal ~0.013s
        ("Scenario 6b (N=1000)", res6b[1000], 15.0),   # Unpatched baseline ~6.3s-7.5s; fail if > 15s
        ("Scenario 7 (N=1000)", res7[1000], 0.10),     # Delta return baseline ~0.032s-0.050s
    ]

    # -------------------------------------------------------------------------
    # Acceptance Targets (v3.0.28 Roadmap) vs Reference Points (Already Achieved)
    # -------------------------------------------------------------------------
    standards_and_references = [
        ("Scenario 5 (N=1000, Delta-Aware Sync)", "< 0.1000s (< 100 µs/op)", "ACCEPTANCE TARGET (v3.0.28)"),
        ("Scenario 6b (N=1000, Full Dict CoW Fix)", "< 1.0000s (< 1000 µs/op)", "ACCEPTANCE TARGET (v3.0.28)"),
        ("Scenario 7 (N=1000, Pattern Delta Return)", "~0.046s-0.050s (< 50 µs/op)", "REFERENCE POINT (ACHIEVED TODAY)"),
    ]

    print("\n" + "=" * 65)
    print("BENCHMARK GATE EVALUATION (Regression Ceilings)")
    print("=" * 65)
    failed = False
    for label, actual, ceiling in regression_ceilings:
        passed = actual <= ceiling
        status = "✅ PASS" if passed else "❌ REGRESSION"
        print(f"  {status} | {label:<35} | {actual:.4f}s (ceiling: {ceiling:.4f}s)")
        if not passed:
            failed = True

    print("\n" + "=" * 65)
    print("TARGET STANDARDS & REFERENCE POINTS")
    print("=" * 65)
    for label, standard, tag in standards_and_references:
        symbol = "🎯" if "ACCEPTANCE" in tag else "📍"
        print(f"  {symbol} {tag:<32} | {label:<35} | {standard}")

    if failed:
        print("\n🚨 BENCHMARK GATE FAILED: Performance thresholds breached!")
        sys.exit(1)
    else:
        print("\n🎉 ALL BENCHMARK REGRESSION GATES PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    main()

