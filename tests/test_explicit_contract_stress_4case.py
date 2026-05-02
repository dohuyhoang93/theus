"""
Comprehensive stress & metric tests for explicit-output-contract pattern.

4 Kịch bản (scenarios):
  1. Mẫu    — basic explicit flow with version tracking and no primitive overwrite
  2. Liên quan — nested hierarchy, list append, const-read / data-write independence
  3. Biên   — 1000-burst sequential, payload growth, p50/p95/p99 latency + memory delta
  4. Xung đột — concurrent cross-field, retry-count measurement, conflict rate
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
# Shared processes
# ---------------------------------------------------------------------------

@process(inputs=["domain.value"], outputs=["domain.value"])
async def p_set_value(ctx, v):
    return v


@process(inputs=["domain.log"], outputs=["domain.log"])
async def p_append_log(ctx, msg):
    current = list(ctx.domain.log)
    current.append(msg)
    return current


@process(
    outputs=[
        "domain.nested.inner.key",
        "domain.nested.sibling.flag",
    ]
)
async def p_set_nested(ctx, key_val, flag_val):
    return key_val, flag_val


@process(inputs=["domain.documents"], outputs=["domain.documents"])
async def p_save_doc(ctx, doc_id, payload):
    docs = dict(ctx.domain.documents)
    docs[doc_id] = payload
    return docs


@process(inputs=["domain.counter_a"], outputs=["domain.counter_a"])
async def p_inc_a(ctx):
    return int(ctx.domain.counter_a) + 1


@process(inputs=["domain.counter_b"], outputs=["domain.counter_b"])
async def p_inc_b(ctx):
    return int(ctx.domain.counter_b) + 1


# ---------------------------------------------------------------------------
# Case 1 — Mẫu: version tracking, no primitive-overwrites-path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case1_mau_version_increments_twice():
    """
    Mẫu: executing a process twice on the same field must increment
    engine.state.version by exactly 2 and leave value = last write.
    """
    engine = TheusEngine(context={"domain": {"value": "init"}})
    engine.register(p_set_value)

    v0 = engine.state.version
    await engine.execute(p_set_value, v="alpha")
    v1 = engine.state.version
    await engine.execute(p_set_value, v="beta")
    v2 = engine.state.version

    assert v1 == v0 + 1, f"After 1st write version should be v0+1, got {v1}"
    assert v2 == v0 + 2, f"After 2nd write version should be v0+2, got {v2}"
    assert engine.state.data["domain"]["value"] == "beta", "Last write must win"


@pytest.mark.asyncio
async def test_case1_mau_state_type_is_not_overwritten_by_ack():
    """
    Mẫu: when a process explicitly returns the new value, the stored type must
    match the returned value — never an ack-string produced by framework internals.
    """
    engine = TheusEngine(context={"domain": {"value": 0}})
    engine.register(p_set_value)

    await engine.execute(p_set_value, v=42)
    stored = engine.state.data["domain"]["value"]
    assert isinstance(stored, int), (
        f"Expected int, got {type(stored).__name__}: {stored!r}"
    )
    assert stored == 42


@pytest.mark.asyncio
async def test_case1_mau_ten_sequential_writes_preserve_monotonicity():
    """
    Mẫu: 10 sequential explicit writes — each version must be strictly greater
    than the previous; final value = value from last write.
    """
    engine = TheusEngine(context={"domain": {"value": 0}})
    engine.register(p_set_value)

    versions = [engine.state.version]
    for i in range(1, 11):
        await engine.execute(p_set_value, v=i)
        versions.append(engine.state.version)

    for j in range(len(versions) - 1):
        assert versions[j + 1] > versions[j], (
            f"Version not monotone at step {j}: {versions[j]} → {versions[j+1]}"
        )
    assert engine.state.data["domain"]["value"] == 10


# ---------------------------------------------------------------------------
# Case 2 — Liên quan: nested hierarchy + list append + sibling preservation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case2_lienquan_nested_write_preserves_sibling_and_untouched():
    """
    Liên quan: writing two deep paths in one explicit process must not destroy
    untouched sibling branches.
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
    engine.register(p_set_nested)

    await engine.execute(p_set_nested, key_val="new_key", flag_val=True)

    assert engine.state.data["domain"]["nested"]["inner"]["key"] == "new_key"
    assert engine.state.data["domain"]["nested"]["inner"]["extra"] == "keep_me"
    assert engine.state.data["domain"]["nested"]["sibling"]["x"] == 99
    assert engine.state.data["domain"]["nested"]["sibling"]["flag"] is True


@pytest.mark.asyncio
async def test_case2_lienquan_list_append_accumulates():
    """
    Liên quan: list-append via explicit return must accumulate all entries
    after multiple executions.
    """
    engine = TheusEngine(context={"domain": {"log": []}})
    engine.register(p_append_log)

    messages = [f"event-{i}" for i in range(20)]
    for msg in messages:
        await engine.execute(p_append_log, msg=msg)

    result = list(engine.state.data["domain"]["log"])
    assert result == messages, f"Log mismatch. Got {result}"


@pytest.mark.asyncio
async def test_case2_lienquan_independent_fields_no_cross_contamination():
    """
    Liên quan: writing field A then field B in separate transactions must leave
    both at their expected values with no cross-contamination.
    """
    engine = TheusEngine(context={"domain": {"value": "init", "log": []}})
    engine.register(p_set_value)
    engine.register(p_append_log)

    await engine.execute(p_set_value, v="hello")
    await engine.execute(p_append_log, msg="note1")
    await engine.execute(p_set_value, v="world")
    await engine.execute(p_append_log, msg="note2")

    assert engine.state.data["domain"]["value"] == "world"
    assert list(engine.state.data["domain"]["log"]) == ["note1", "note2"]


# ---------------------------------------------------------------------------
# Case 3 — Biên: 1000-burst, payload growth, latency p50/p95/p99, memory delta
# ---------------------------------------------------------------------------

BURST_N = 1000


@pytest.mark.asyncio
async def test_case3_bien_burst_no_document_loss():
    """
    Biên: 1000 sequential explicit saves must produce exactly 1000 entries —
    zero loss, zero overwrite across different doc-ids.
    """
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(p_save_doc)

    for i in range(BURST_N):
        await engine.execute(
            p_save_doc,
            doc_id=f"DOC-{i:04d}",
            payload={"index": i, "tag": f"batch-{i // 100}"},
        )

    docs = dict(engine.state.data["domain"]["documents"])
    assert len(docs) == BURST_N, f"Expected {BURST_N} docs, got {len(docs)}"

    missing = [f"DOC-{i:04d}" for i in range(BURST_N) if f"DOC-{i:04d}" not in docs]
    assert not missing, f"Missing {len(missing)} docs: {missing[:5]}…"


@pytest.mark.asyncio
async def test_case3_bien_latency_metrics():
    """
    Biên: measure per-transaction latency for 200 writes.
    Assert p50 < 10 ms, p95 < 50 ms, p99 < 100 ms (wall-clock).
    """
    engine = TheusEngine(context={"domain": {"value": 0}})
    engine.register(p_set_value)

    N = 200
    latencies_ms: list[float] = []

    for i in range(N):
        t0 = time.perf_counter()
        await engine.execute(p_set_value, v=i)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    p50 = statistics.median(latencies_ms)
    p95 = sorted(latencies_ms)[int(N * 0.95)]
    p99 = sorted(latencies_ms)[int(N * 0.99)]

    print(f"\n[Case 3 Latency] p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms")

    assert p50 < 10, f"p50 latency too high: {p50:.2f} ms"
    assert p95 < 50, f"p95 latency too high: {p95:.2f} ms"
    assert p99 < 100, f"p99 latency too high: {p99:.2f} ms"


@pytest.mark.asyncio
async def test_case3_bien_memory_delta_bounded():
    """
    Biên: memory allocated during 500 explicit doc-saves must stay under 50 MB.
    This guards against accidental deep-copy accumulation in state.
    """
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(p_save_doc)

    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()

    N = 500
    for i in range(N):
        await engine.execute(
            p_save_doc,
            doc_id=f"D{i:05d}",
            payload={"i": i, "data": "x" * 128},
        )

    snap2 = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snap2.compare_to(snap1, "lineno")
    total_kb = sum(s.size_diff for s in top_stats) / 1024
    total_mb = total_kb / 1024

    print(f"\n[Case 3 Memory] net delta for {N} saves: {total_mb:.2f} MB")

    assert total_mb < 50, (
        f"Memory delta {total_mb:.2f} MB exceeds 50 MB limit — possible CoW accumulation"
    )


@pytest.mark.asyncio
async def test_case3_bien_payload_growth_correctness():
    """
    Biên: payload size grows per write (simulating real workload growth).
    Final document must reflect the largest/last payload written.
    """
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(p_save_doc)

    N = 100
    for i in range(N):
        payload = {"i": i, "blob": "A" * (i * 10)}
        await engine.execute(p_save_doc, doc_id="single", payload=payload)

    final = engine.state.data["domain"]["documents"]["single"]
    assert final["i"] == N - 1
    assert len(final["blob"]) == (N - 1) * 10


# ---------------------------------------------------------------------------
# Case 4 — Xung đột: concurrent cross-field, retry measurement, conflict rate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case4_xungdot_concurrent_independent_fields_converge():
    """
    Xung đột: concurrent writes to counter_a and counter_b (independent fields)
    must both reach the target count — Smart CAS must not reject valid updates.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(p_inc_a)
    engine.register(p_inc_b)

    N = 50
    for _ in range(N):
        await asyncio.gather(
            engine.execute(p_inc_a, retries=10),
            engine.execute(p_inc_b, retries=10),
        )

    ca = int(engine.state.data["domain"]["counter_a"])
    cb = int(engine.state.data["domain"]["counter_b"])

    assert ca == N, f"counter_a expected {N}, got {ca}"
    assert cb == N, f"counter_b expected {N}, got {cb}"


@pytest.mark.asyncio
async def test_case4_xungdot_conflict_rate_measured():
    """
    Xung đột: wrap execute() to count retries/conflicts and compute conflict rate.
    Conflict rate for independent fields should stay below 5 %.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(p_inc_a)
    engine.register(p_inc_b)

    retry_counts: Counter = Counter()
    N = 40
    max_retries = 8

    async def tracked_inc(proc_fn, key: str):
        orig_execute = engine.execute

        # Wrap to count retries via retry backoff side effect — use a simple
        # counter approach: compare version before/after to detect CAS re-spin.
        v_before = engine.state.version
        await orig_execute(proc_fn, retries=max_retries)
        v_after = engine.state.version
        # Each committed write increments version by 1; extra increments = retries
        extra = max(0, (v_after - v_before) - 1)
        retry_counts[key] += extra

    for _ in range(N):
        await asyncio.gather(
            tracked_inc(p_inc_a, "a"),
            tracked_inc(p_inc_b, "b"),
        )

    total_ops = N * 2
    total_retries = sum(retry_counts.values())
    conflict_rate = total_retries / total_ops

    print(
        f"\n[Case 4 Conflicts] retries_a={retry_counts['a']} "
        f"retries_b={retry_counts['b']} "
        f"rate={conflict_rate:.1%}"
    )

    ca = int(engine.state.data["domain"]["counter_a"])
    cb = int(engine.state.data["domain"]["counter_b"])
    assert ca == N, f"counter_a={ca} expected {N}"
    assert cb == N, f"counter_b={cb} expected {N}"
    assert conflict_rate < 0.05, (
        f"Conflict rate {conflict_rate:.1%} exceeds 5 % for independent fields"
    )


@pytest.mark.asyncio
async def test_case4_xungdot_high_concurrency_burst():
    """
    Xung đột: fan-out 20 concurrent increments on counter_a simultaneously.
    All 20 must commit eventually — tests retry convergence under contention.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0}})
    engine.register(p_inc_a)

    N = 20
    await asyncio.gather(*[engine.execute(p_inc_a, retries=20) for _ in range(N)])

    result = int(engine.state.data["domain"]["counter_a"])
    assert result == N, f"Expected {N} increments committed, got {result}"


@pytest.mark.asyncio
async def test_case4_xungdot_version_increases_by_total_commits():
    """
    Xung đột: version delta after N concurrent independent-field pairs must be
    exactly 2*N (one commit per field per round, no phantom increments).
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(p_inc_a)
    engine.register(p_inc_b)

    v0 = engine.state.version
    N = 20
    for _ in range(N):
        await asyncio.gather(
            engine.execute(p_inc_a, retries=10),
            engine.execute(p_inc_b, retries=10),
        )
    vN = engine.state.version

    assert vN == v0 + 2 * N, (
        f"Expected version {v0 + 2*N}, got {vN} "
        f"(delta={vN - v0}, expected {2*N})"
    )
