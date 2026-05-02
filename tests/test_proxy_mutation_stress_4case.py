"""
Comprehensive stress & metric tests for proxy-mutation contract pattern.

Tương đương test_explicit_contract_stress_4case.py nhưng cho pattern:
    ctx.domain.field = value   (proxy mutation)
    return "ok"                (ack string — không phải data)

4 Kịch bản:
  1. Mẫu    — basic proxy mutation: version tracking, ack không ghi đè state
  2. Liên quan — nested deep-path, list append, independent fields, const/data independence
  3. Biên   — 1000-burst sequential, payload growth, p50/p95/p99 latency + memory delta
  4. Xung đột — concurrent cross-field, proxy-increment, conflict rate, version = 2N
"""

import asyncio
import statistics
import time
import tracemalloc
from collections import Counter

import pytest

from theus.contracts import process
from theus.engine import TheusEngine


# ---------------------------------------------------------------------------
# Proxy-mutation processes (mutate ctx, return ack string)
# ---------------------------------------------------------------------------

@process(outputs=["domain.value"])
async def pm_set_value(ctx, v):
    ctx.domain.value = v
    return "ok"


@process(outputs=["domain.log"])
async def pm_append_log(ctx, msg):
    ctx.domain.log.append(msg)
    return "ok"


@process(outputs=["domain.nested.inner.key", "domain.nested.sibling.flag"])
async def pm_set_nested(ctx, key_val, flag_val):
    ctx.domain.nested.inner.key = key_val
    ctx.domain.nested.sibling.flag = flag_val
    return None  # proxy mutations are sole source of truth


@process(outputs=["domain.documents"])
async def pm_save_doc(ctx, doc_id, payload):
    # Update by key in place to avoid rebuilding/copying the whole documents
    # map on every write during stress scenarios.
    ctx.domain.documents[doc_id] = payload
    return "ok"


@process(outputs=["domain.counter_a"])
async def pm_inc_a(ctx):
    ctx.domain.counter_a = int(ctx.domain.counter_a) + 1
    return "ok"


@process(outputs=["domain.counter_b"])
async def pm_inc_b(ctx):
    ctx.domain.counter_b = int(ctx.domain.counter_b) + 1
    return "ok"


@process(outputs=["domain.data_items"])
async def pm_append_items(ctx, item):
    items = list(ctx.domain.data_items)
    items.append(item)
    ctx.domain.data_items = items
    return "done"


# ---------------------------------------------------------------------------
# Case 1 — Mẫu: ack không ghi đè state, version tăng đúng
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case1_mau_ack_does_not_overwrite_proxy_value():
    """
    Mẫu: process mutates via proxy and returns ack "ok".
    State must reflect the proxy mutation, NOT the ack string.
    """
    engine = TheusEngine(context={"domain": {"value": "init"}})
    engine.register(pm_set_value)

    result = await engine.execute(pm_set_value, v="hello")

    assert result == "ok", "execute() should still return the raw ack string"
    stored = engine.state.data["domain"]["value"]
    assert stored == "hello", (
        f"State must hold proxy-written value 'hello', not ack '{stored}'"
    )
    assert not isinstance(stored, str) or stored != "ok", (
        "Ack 'ok' must never leak into state"
    )


@pytest.mark.asyncio
async def test_case1_mau_version_increments_on_proxy_mutation():
    """
    Mẫu: version must increment exactly once per proxy mutation commit.
    """
    engine = TheusEngine(context={"domain": {"value": 0}})
    engine.register(pm_set_value)

    v0 = engine.state.version
    await engine.execute(pm_set_value, v=1)
    v1 = engine.state.version
    await engine.execute(pm_set_value, v=2)
    v2 = engine.state.version

    assert v1 == v0 + 1
    assert v2 == v0 + 2
    assert engine.state.data["domain"]["value"] == 2


@pytest.mark.asyncio
async def test_case1_mau_ten_sequential_proxy_writes_monotone():
    """
    Mẫu: 10 proxy-mutation writes — version strictly monotone, final value = last.
    """
    engine = TheusEngine(context={"domain": {"value": 0}})
    engine.register(pm_set_value)

    versions = [engine.state.version]
    for i in range(1, 11):
        await engine.execute(pm_set_value, v=i)
        versions.append(engine.state.version)

    for j in range(len(versions) - 1):
        assert versions[j + 1] > versions[j], (
            f"Version not monotone at step {j}: {versions[j]} → {versions[j+1]}"
        )
    assert engine.state.data["domain"]["value"] == 10


@pytest.mark.asyncio
async def test_case1_mau_none_return_also_defers_to_proxy():
    """
    Mẫu: process returning None must also preserve proxy mutation.
    (Regression: None was already handled; make sure it still works with hybrid fix.)
    """
    @process(outputs=["domain.value"])
    async def pm_set_none_return(ctx, v):
        ctx.domain.value = v
        return None

    engine = TheusEngine(context={"domain": {"value": "init"}})
    engine.register(pm_set_none_return)

    await engine.execute(pm_set_none_return, v="from_proxy")
    assert engine.state.data["domain"]["value"] == "from_proxy"


# ---------------------------------------------------------------------------
# Case 2 — Liên quan: nested, list append, independent fields, const/data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case2_lienquan_nested_proxy_preserves_sibling():
    """
    Liên quan: proxy-mutating two deep paths must not destroy untouched siblings.
    """
    engine = TheusEngine(
        context={
            "domain": {
                "nested": {
                    "inner": {"key": "old_key", "extra": "keep_me"},
                    "sibling": {"x": 99},
                }
            }
        }
    )
    engine.register(pm_set_nested)

    await engine.execute(pm_set_nested, key_val="new_key", flag_val=True)

    assert engine.state.data["domain"]["nested"]["inner"]["key"] == "new_key"
    assert engine.state.data["domain"]["nested"]["inner"]["extra"] == "keep_me"
    assert engine.state.data["domain"]["nested"]["sibling"]["x"] == 99
    assert engine.state.data["domain"]["nested"]["sibling"]["flag"] is True


@pytest.mark.asyncio
async def test_case2_lienquan_proxy_list_append_accumulates():
    """
    Liên quan: proxy list.append() writes must accumulate across executions.
    """
    engine = TheusEngine(context={"domain": {"log": []}})
    engine.register(pm_append_log)

    messages = [f"event-{i}" for i in range(20)]
    for msg in messages:
        await engine.execute(pm_append_log, msg=msg)

    result = list(engine.state.data["domain"]["log"])
    assert result == messages, f"Log mismatch. Got {result}"


@pytest.mark.asyncio
async def test_case2_lienquan_proxy_and_explicit_coexist():
    """
    Liên quan: proxy mutation on field A and explicit return on field B in separate
    transactions must not interfere with each other.
    """
    @process(outputs=["domain.tag"])
    async def p_set_tag_explicit(ctx, tag):
        return tag  # explicit — no proxy mutation

    engine = TheusEngine(context={"domain": {"value": "init", "tag": "none"}})
    engine.register(pm_set_value)
    engine.register(p_set_tag_explicit)

    await engine.execute(pm_set_value, v="proxy_val")
    await engine.execute(p_set_tag_explicit, tag="explicit_tag")
    await engine.execute(pm_set_value, v="proxy_val2")

    assert engine.state.data["domain"]["value"] == "proxy_val2"
    assert engine.state.data["domain"]["tag"] == "explicit_tag"


@pytest.mark.asyncio
async def test_case2_lienquan_const_field_not_polluted_by_proxy_ack():
    """
    Liên quan: process mutating data_items via proxy + returning 'done' must leave
    data_items correct even when const_ field coexists in same namespace.
    (Regression guard for test_const_does_not_affect_normal_data pattern.)
    """
    engine = TheusEngine(
        context={
            "domain": {
                "const_max_retries": 3,
                "data_items": [],
            }
        }
    )
    engine.register(pm_append_items)

    result = await engine.execute(pm_append_items, item="processed")

    assert result == "done"
    items = engine.state.data["domain"]["data_items"]
    assert items == ["processed"], (
        f"data_items should be ['processed'], not {items!r}"
    )
    # const_ field must be untouched
    assert engine.state.data["domain"]["const_max_retries"] == 3


# ---------------------------------------------------------------------------
# Case 3 — Biên: 1000-burst, payload growth, latency + memory metrics
# ---------------------------------------------------------------------------

BURST_N = 1000


@pytest.mark.asyncio
async def test_case3_bien_burst_proxy_no_document_loss():
    """
    Biên: 1000 proxy-mutation saves must produce exactly 1000 entries — zero loss.
    """
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(pm_save_doc)

    for i in range(BURST_N):
        await engine.execute(
            pm_save_doc,
            doc_id=f"DOC-{i:04d}",
            payload={"index": i, "tag": f"batch-{i // 100}"},
        )

    docs = dict(engine.state.data["domain"]["documents"])
    assert len(docs) == BURST_N, f"Expected {BURST_N} docs, got {len(docs)}"

    missing = [f"DOC-{i:04d}" for i in range(BURST_N) if f"DOC-{i:04d}" not in docs]
    assert not missing, f"Missing {len(missing)} docs: {missing[:5]}…"


@pytest.mark.asyncio
async def test_case3_bien_proxy_latency_metrics():
    """
    Biên: per-transaction latency for 200 proxy-mutation writes.
    p50 < 10 ms, p95 < 50 ms, p99 < 100 ms.
    """
    engine = TheusEngine(context={"domain": {"value": 0}})
    engine.register(pm_set_value)

    N = 200
    latencies_ms: list[float] = []

    for i in range(N):
        t0 = time.perf_counter()
        await engine.execute(pm_set_value, v=i)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    p50 = statistics.median(latencies_ms)
    p95 = sorted(latencies_ms)[int(N * 0.95)]
    p99 = sorted(latencies_ms)[int(N * 0.99)]

    print(f"\n[Case 3 Proxy Latency] p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms")

    assert p50 < 10, f"p50 latency too high: {p50:.2f} ms"
    assert p95 < 50, f"p95 latency too high: {p95:.2f} ms"
    assert p99 < 100, f"p99 latency too high: {p99:.2f} ms"


@pytest.mark.asyncio
async def test_case3_bien_proxy_memory_delta_bounded():
    """
    Biên: memory allocated during 500 proxy-mutation doc-saves under 50 MB.
    Guards against proxy-object accumulation or snapshot retention leaks.
    """
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(pm_save_doc)

    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()

    N = 300
    for i in range(N):
        await engine.execute(
            pm_save_doc,
            doc_id=f"D{i:05d}",
            payload={"i": i, "data": "x" * 64},
        )

    snap2 = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snap2.compare_to(snap1, "lineno")
    total_mb = sum(s.size_diff for s in top_stats) / (1024 * 1024)

    print(f"\n[Case 3 Proxy Memory] net delta for {N} saves: {total_mb:.2f} MB")

    assert total_mb < 50, (
        f"Memory delta {total_mb:.2f} MB exceeds 50 MB limit — possible proxy accumulation"
    )


@pytest.mark.asyncio
async def test_case3_bien_proxy_payload_growth_correctness():
    """
    Biên: growing-payload proxy writes — final value = last write, correct size.
    """
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(pm_save_doc)

    N = 100
    for i in range(N):
        payload = {"i": i, "blob": "B" * (i * 10)}
        await engine.execute(pm_save_doc, doc_id="single", payload=payload)

    final = engine.state.data["domain"]["documents"]["single"]
    assert final["i"] == N - 1
    assert len(final["blob"]) == (N - 1) * 10


# ---------------------------------------------------------------------------
# Case 4 — Xung đột: concurrent cross-field, conflict rate, version = 2N
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case4_xungdot_proxy_concurrent_independent_fields_converge():
    """
    Xung đột: concurrent proxy-mutations on counter_a and counter_b must both
    reach target count — no commit lost, no ack overwrite.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(pm_inc_a)
    engine.register(pm_inc_b)

    N = 50
    for _ in range(N):
        await asyncio.gather(
            engine.execute(pm_inc_a, retries=10),
            engine.execute(pm_inc_b, retries=10),
        )

    ca = int(engine.state.data["domain"]["counter_a"])
    cb = int(engine.state.data["domain"]["counter_b"])
    assert ca == N, f"counter_a expected {N}, got {ca}"
    assert cb == N, f"counter_b expected {N}, got {cb}"


@pytest.mark.asyncio
async def test_case4_xungdot_proxy_conflict_rate_measured():
    """
    Xung đột: measure conflict rate for concurrent proxy-mutation on independent fields.
    Must stay below 5 %.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(pm_inc_a)
    engine.register(pm_inc_b)

    retry_counts: Counter = Counter()
    N = 40
    max_retries = 8

    async def tracked_inc(proc_fn, key: str):
        v_before = engine.state.version
        await engine.execute(proc_fn, retries=max_retries)
        v_after = engine.state.version
        retry_counts[key] += max(0, (v_after - v_before) - 1)

    for _ in range(N):
        await asyncio.gather(
            tracked_inc(pm_inc_a, "a"),
            tracked_inc(pm_inc_b, "b"),
        )

    total_ops = N * 2
    conflict_rate = sum(retry_counts.values()) / total_ops

    print(
        f"\n[Case 4 Proxy Conflicts] retries_a={retry_counts['a']} "
        f"retries_b={retry_counts['b']} rate={conflict_rate:.1%}"
    )

    ca = int(engine.state.data["domain"]["counter_a"])
    cb = int(engine.state.data["domain"]["counter_b"])
    assert ca == N, f"counter_a={ca} expected {N}"
    assert cb == N, f"counter_b={cb} expected {N}"
    assert conflict_rate < 0.05, (
        f"Conflict rate {conflict_rate:.1%} exceeds 5% for independent fields"
    )


@pytest.mark.asyncio
async def test_case4_xungdot_proxy_high_concurrency_burst():
    """
    Xung đột: fan-out 20 concurrent proxy-increments on the same counter.
    All 20 must commit (tests retry convergence under contention).
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0}})
    engine.register(pm_inc_a)

    N = 20
    await asyncio.gather(*[engine.execute(pm_inc_a, retries=20) for _ in range(N)])

    result = int(engine.state.data["domain"]["counter_a"])
    assert result == N, f"Expected {N} proxy-increments committed, got {result}"


@pytest.mark.asyncio
async def test_case4_xungdot_proxy_version_equals_2n_commits():
    """
    Xung đột: version delta after N concurrent independent-field proxy-pairs
    must be exactly 2*N — no phantom increments from ack re-mapping.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(pm_inc_a)
    engine.register(pm_inc_b)

    v0 = engine.state.version
    N = 20
    for _ in range(N):
        await asyncio.gather(
            engine.execute(pm_inc_a, retries=10),
            engine.execute(pm_inc_b, retries=10),
        )
    vN = engine.state.version

    assert vN == v0 + 2 * N, (
        f"Expected version {v0 + 2*N}, got {vN} "
        f"(delta={vN - v0}, expected {2*N})"
    )
