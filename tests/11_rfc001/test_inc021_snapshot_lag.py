"""
test_inc021_snapshot_lag.py
===========================
Kiểm chứng các giả định và lập luận trong phân tích INC-021
"Transaction Snapshot Lag Causes Sequential Document Loss"

MỤC TIÊU:
    Xác định BUG CÓ TỒN TẠI hay không, và nếu có, cơ chế nào gây ra.

CÁC GIẢ ĐỊNH CẦN KIỂM CHỨNG:
    H1 (INC): CoW return pattern gây data loss từ lần execute thứ 3 trở đi.
    H2 (INC): Hiện tượng 100% deterministic, không phải flaky.
    H3 (Analysis): self.state cache (version-based) tự invalidate đúng sau mỗi commit.
    H4 (Analysis): Merge base (getattr(self.state, key)) phản ánh version mới nhất.
    H5 (INC): Proxy Mutation pattern loại bỏ hoàn toàn vấn đề.
    H6 (Analysis): v3.1.5 `pending_data[root] = {}` chỉ áp dụng cho StateUpdate.data path.
"""

import pytest
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from theus import TheusEngine, process
from theus.structures import StateUpdate
from theus.context import BaseSystemContext, BaseDomainContext


# ─────────────────────────── SHARED FIXTURES ───────────────────────────────

@dataclass
class DocDomain(BaseDomainContext):
    documents: Dict[str, Any] = field(default_factory=dict)
    outbox_queue: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DocContext(BaseSystemContext):
    domain: DocDomain = field(default_factory=DocDomain)


def _make_engine() -> TheusEngine:
    """Fresh engine với DocContext."""
    ctx = DocContext(domain=DocDomain(documents={}, outbox_queue=[]))
    return TheusEngine(ctx, strict_guards=False)


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 1: Kiểm chứng H1 & H2 — CoW return pattern có thực sự gây data loss?
# ═══════════════════════════════════════════════════════════════════════════

@process(
    inputs=["domain.documents", "domain.outbox_queue"],
    outputs=["domain.documents", "domain.outbox_queue"],
    errors=["ValueError"],
    semantic="effect",
)
def save_document_cow(ctx, doc_id: str, metadata: dict):
    """
    Process dùng CoW return pattern — đây là PATTERN BỊ BUG trong INC-021.
    Clone snapshot, thêm entry, return full dict.
    """
    # CoW: Clone snapshot
    new_docs: Dict[str, Any] = dict(ctx.domain.documents)
    new_docs[doc_id] = {
        "metadata": metadata,
        "status": "active",
        "timestamp": time.time(),
    }
    new_queue: List[Dict[str, Any]] = list(ctx.domain.outbox_queue)
    new_queue.append({"action": "save", "doc_id": doc_id})
    return new_docs, new_queue


@pytest.mark.asyncio
async def test_H1_cow_pattern_5_sequential_saves():
    """
    H1: CoW return pattern gây data loss từ lần execute thứ 3 trở đi.

    Nếu H1 ĐÚNG  → sau 5 saves, state chỉ chứa <5 documents.
    Nếu H1 SAI   → sau 5 saves, state chứa đủ 5 documents.
    """
    engine = _make_engine()
    engine.register(save_document_cow)

    doc_ids = [f"BATCH-{i:03d}" for i in range(5)]

    for doc_id in doc_ids:
        await engine.execute("save_document_cow", doc_id=doc_id, metadata={"title": doc_id})

    final_docs = dict(engine.state.data["domain"]["documents"])
    found = list(final_docs.keys())

    print(f"\n[H1] Documents in state after 5 CoW saves: {found}")
    print(f"[H1] Expected: {doc_ids}")

    # Assertion phân nhánh: giúp phân biệt "bug tồn tại" vs "bug không tồn tại"
    missing = [d for d in doc_ids if d not in found]
    if missing:
        # Bug xác nhận: INC-021 đúng
        print(f"[H1 CONFIRMED] BUG EXISTS — missing documents: {missing}")
        pytest.fail(
            f"CoW pattern causes data loss: {len(found)}/5 documents saved. "
            f"Missing: {missing}. INC-021 is a real bug."
        )
    else:
        # Bug không xảy ra: hoặc đã được fix, hoặc H1 sai
        print("[H1 REFUTED] All 5 documents present — CoW data loss NOT observed.")
        assert len(found) == 5


@pytest.mark.asyncio
async def test_H2_cow_determinism_across_runs():
    """
    H2: Hiện tượng 100% deterministic (không phải race condition hay flaky).

    Chạy 3 lần độc lập, quan sát kết quả có nhất quán không.
    Nếu H2 ĐÚNG  → cả 3 lần đều thiếu cùng documents.
    Nếu H2 SAI   → kết quả ngẫu nhiên (flaky).
    """
    results = []
    for run in range(3):
        engine = _make_engine()
        engine.register(save_document_cow)
        for i in range(5):
            await engine.execute(
                "save_document_cow",
                doc_id=f"DOC-{i:03d}",
                metadata={"run": run, "idx": i},
            )
        final = set(engine.state.data["domain"]["documents"].keys())
        results.append(final)
        print(f"[H2] Run {run}: {sorted(final)}")

    # So sánh 3 lần chạy: nếu deterministic, kết quả phải giống nhau
    assert results[0] == results[1] == results[2], (
        f"[H2 REFUTED] Results vary across runs — behavior is NON-DETERMINISTIC.\n"
        f"Run 0: {results[0]}\nRun 1: {results[1]}\nRun 2: {results[2]}"
    )
    print(f"[H2 CONFIRMED] Deterministic across 3 runs: {sorted(results[0])}")


@pytest.mark.asyncio
async def test_H1_boundary_first_two_executes_safe():
    """
    Bổ sung cho H1: INC-021 nói BATCH-000 và BATCH-001 luôn sống sót.
    Kiểm tra ranh giới: 2 executes phải đúng, chỉ từ lần 3 mới mất.
    """
    engine = _make_engine()
    engine.register(save_document_cow)

    # Chỉ chạy 2 lần
    for i in range(2):
        await engine.execute(
            "save_document_cow", doc_id=f"TWO-{i:03d}", metadata={}
        )

    final = dict(engine.state.data["domain"]["documents"])
    print(f"[H1-Boundary] After 2 saves: {list(final.keys())}")

    # Nếu bug tồn tại thì 2 documents này phải có mặt
    assert "TWO-000" in final, "TWO-000 must survive (per INC-021 analysis)"
    assert "TWO-001" in final, "TWO-001 must survive (per INC-021 analysis)"
    assert len(final) == 2


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 2: Kiểm chứng H3 — self.state cache invalidation
# ═══════════════════════════════════════════════════════════════════════════

@process(
    inputs=["domain.documents"],
    outputs=["domain.documents"],
    semantic="effect",
)
def append_one_doc(ctx, doc_id: str):
    """Process đơn giản thêm 1 document, dùng proxy mutation."""
    ctx.domain.documents[doc_id] = {"ts": time.time()}
    return None


@pytest.mark.asyncio
async def test_H3_state_cache_version_increments_after_each_execute():
    """
    H3: self.state cache tự invalidate sau mỗi commit.

    Kiểm tra engine.state.version tăng đúng sau mỗi execute().
    Nếu H3 ĐÚNG  → version tăng monotonically: 0 → 1 → 2 → ...
    Nếu H3 SAI   → version đứng yên hoặc bị cache stale.
    """
    engine = _make_engine()
    engine.register(append_one_doc)

    versions = [engine.state.version]

    for i in range(4):
        await engine.execute("append_one_doc", doc_id=f"VER-{i:03d}")
        v = engine.state.version
        versions.append(v)
        print(f"[H3] After execute #{i}: version={v}")

    print(f"[H3] Version history: {versions}")

    # Phải tăng đều, không được có giá trị lặp lại
    for i in range(1, len(versions)):
        assert versions[i] > versions[i - 1], (
            f"[H3 FAIL] Cache NOT invalidated: version stuck at {versions[i - 1]} "
            f"after execute #{i - 1}"
        )
    print("[H3 CONFIRMED] self.state cache invalidates correctly after each commit.")


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 3: Kiểm chứng H4 — Merge base đọc version mới nhất
# ═══════════════════════════════════════════════════════════════════════════

# Dùng biến ngoài để capture snapshot bên trong process
_captured_snapshots: List[Dict[str, Any]] = []


@process(
    inputs=["domain.documents", "domain.outbox_queue"],
    outputs=["domain.documents", "domain.outbox_queue"],
    semantic="effect",
)
def save_document_cow_with_capture(ctx, doc_id: str):
    """
    CoW process với introspection: ghi lại snapshot `ctx.domain.documents`
    tại thời điểm process chạy, TRƯỚC khi thêm entry mới.
    """
    snapshot = dict(ctx.domain.documents)
    _captured_snapshots.append({"doc_id": doc_id, "snapshot_keys": list(snapshot.keys())})

    new_docs = dict(snapshot)
    new_docs[doc_id] = {"ts": time.time()}
    new_queue = list(ctx.domain.outbox_queue) + [{"doc_id": doc_id}]
    return new_docs, new_queue


@pytest.mark.asyncio
async def test_H4_merge_base_snapshot_version():
    """
    H4: Merge base (ctx.domain.documents) phản ánh version mới nhất khi process chạy.

    Kiểm tra: snapshot mà process thấy ở lần N có chứa entry từ lần N-1 không?

    Nếu H4 ĐÚNG  → snapshot luôn up-to-date: lần N thấy N-1 entries.
    Nếu H4 SAI   → snapshot stale: lần N thấy ít hơn N-1 entries (INC-021 mechanism).
    """
    global _captured_snapshots
    _captured_snapshots = []

    engine = _make_engine()
    engine.register(save_document_cow_with_capture)

    doc_ids = [f"CAP-{i:03d}" for i in range(5)]
    for doc_id in doc_ids:
        await engine.execute("save_document_cow_with_capture", doc_id=doc_id)

    print("\n[H4] Snapshot seen by each process invocation:")
    lag_found = False
    for i, capture in enumerate(_captured_snapshots):
        expected_count = i  # execute N phải thấy N entries từ các execute trước
        actual_count = len(capture["snapshot_keys"])
        lag = expected_count - actual_count
        status = "✅" if lag == 0 else f"⚠️ LAG={lag}"
        print(
            f"  Execute #{i} ({capture['doc_id']}): "
            f"snapshot={capture['snapshot_keys']} | "
            f"expected={expected_count} entries | actual={actual_count} | {status}"
        )
        if lag > 0:
            lag_found = True

    if lag_found:
        print("[H4 CONFIRMED — SNAPSHOT LAG EXISTS] Process sees stale state.")
        # Không fail ngay — để test khác verify hậu quả
        # Đây là bằng chứng cơ chế
    else:
        print("[H4 REFUTED] No snapshot lag — process always sees current state.")

    # Test này luôn pass vì mục đích là QUAN SÁT, không assert fail/pass
    # Kết quả được in để phân tích
    assert len(_captured_snapshots) == 5, "All 5 captures must exist"


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 4: Kiểm chứng H5 — Proxy Mutation pattern fix được vấn đề
# ═══════════════════════════════════════════════════════════════════════════

@process(
    inputs=["domain.documents", "domain.outbox_queue"],
    outputs=["domain.documents", "domain.outbox_queue"],
    errors=["ValueError"],
    semantic="effect",
)
def save_document_proxy(ctx, doc_id: str, metadata: dict):
    """
    Process dùng Proxy Mutation — đây là FIX pattern.
    Ghi trực tiếp qua proxy, return None.
    """
    ctx.domain.documents[doc_id] = {
        "metadata": metadata,
        "status": "active",
        "timestamp": time.time(),
    }
    ctx.domain.outbox_queue.append({"action": "save", "doc_id": doc_id})
    return None


@pytest.mark.asyncio
async def test_H5_proxy_mutation_5_sequential_saves():
    """
    H5: Proxy Mutation pattern loại bỏ hoàn toàn vấn đề data loss.

    Nếu H5 ĐÚNG  → cả 5 documents có mặt trong state.
    Nếu H5 SAI   → vẫn bị mất (fix không hiệu quả).
    """
    engine = _make_engine()
    engine.register(save_document_proxy)

    doc_ids = [f"PROXY-{i:03d}" for i in range(5)]
    for doc_id in doc_ids:
        await engine.execute("save_document_proxy", doc_id=doc_id, metadata={"title": doc_id})

    final_docs = dict(engine.state.data["domain"]["documents"])
    found = list(final_docs.keys())
    print(f"\n[H5] Documents after 5 Proxy saves: {found}")

    missing = [d for d in doc_ids if d not in found]
    assert not missing, (
        f"[H5 FAIL] Proxy Mutation still loses documents: {missing}"
    )
    assert len(found) == 5, f"Expected 5 documents, got {len(found)}"
    print("[H5 CONFIRMED] Proxy Mutation saves all 5 documents correctly.")


@pytest.mark.asyncio
async def test_H5_proxy_mutation_outbox_also_accumulates():
    """
    H5 Addendum: INC-021 ghi nhận outbox_queue cũng bị silent data loss với CoW.
    Kiểm tra proxy mutation fix cả outbox.
    """
    engine = _make_engine()
    engine.register(save_document_proxy)

    for i in range(5):
        await engine.execute(
            "save_document_proxy", doc_id=f"OB-{i:03d}", metadata={}
        )

    outbox = list(engine.state.data["domain"]["outbox_queue"])
    print(f"\n[H5-Outbox] Queue length: {len(outbox)}, entries: {[e['doc_id'] for e in outbox]}")

    assert len(outbox) == 5, (
        f"[H5-Outbox FAIL] Expected 5 outbox entries, got {len(outbox)}. "
        f"Entries: {outbox}"
    )
    print("[H5-Outbox CONFIRMED] All 5 outbox messages preserved.")


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 5: Kiểm chứng H6 — v3.1.5 `pending_data[root] = {}` path
# ═══════════════════════════════════════════════════════════════════════════

@process(
    inputs=["domain.documents"],
    outputs=["domain.documents"],
    semantic="effect",
)
def save_via_stateupdate(ctx, doc_id: str):
    """
    Process dùng StateUpdate với result.data path (v3.1.5 path).
    Theo phân tích: path này dùng `pending_data[root] = {}` (empty dict trigger Deep Merge).

    Test dùng Proxy Mutation + StateUpdate để không trigger deepcopy failure.
    Mục đích: kiểm tra StateUpdate path có bảo toàn accumulated data không.
    """
    # Proxy Mutation để ghi entry
    ctx.domain.documents[doc_id] = {"ts": time.time(), "via": "stateupdate_path"}
    # Return StateUpdate explicit để trigger commit path khác với implicit CoW
    return StateUpdate(key="domain.documents", val=dict(ctx.domain.documents))


@pytest.mark.asyncio
async def test_H6_stateupdate_data_path_5_saves():
    """
    H6: StateUpdate.data path (v3.1.5) có bị cùng vấn đề không?

    Theo phân tích: path này dùng `pending_data[root] = {}` (empty dict trigger Deep Merge).
    Điều này khác CoW vì Rust Deep Merge sẽ MERGE thay vì REPLACE.

    Nếu H6 ĐÚNG  → StateUpdate.data path hoạt động đúng (Rust Deep Merge bảo vệ).
    Nếu H6 SAI   → StateUpdate.data path cũng bị data loss.
    """
    engine = _make_engine()
    engine.register(save_via_stateupdate)

    doc_ids = [f"SU-{i:03d}" for i in range(5)]
    for doc_id in doc_ids:
        await engine.execute("save_via_stateupdate", doc_id=doc_id)

    final_docs = dict(engine.state.data["domain"]["documents"])
    found = list(final_docs.keys())
    print(f"\n[H6] Documents via StateUpdate.data: {found}")

    missing = [d for d in doc_ids if d not in found]
    if missing:
        print(f"[H6 FAIL] StateUpdate.data path also loses documents: {missing}")
        pytest.fail(
            f"StateUpdate.data path causes data loss: missing {missing}. "
            f"v3.1.5 Rust Deep Merge not protecting against CoW-equivalent loss."
        )
    else:
        print("[H6 CONFIRMED] StateUpdate.data path (Deep Merge) accumulates all 5 docs correctly.")
        assert len(found) == 5


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 6: So sánh trực tiếp CoW vs Proxy — Comparative Proof
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_comparative_cow_vs_proxy_same_engine():
    """
    Comparative Test: Đặt CoW và Proxy side-by-side với cùng số lần execute.

    Mục đích: Nếu CoW gây mất data mà Proxy không mất, đây là bằng chứng
    rõ ràng nhất rằng vấn đề nằm ở return pattern, không phải infrastructure.
    """
    N = 5

    # --- Run 1: CoW ---
    engine_cow = _make_engine()
    engine_cow.register(save_document_cow)
    for i in range(N):
        await engine_cow.execute(
            "save_document_cow", doc_id=f"CMP-{i:03d}", metadata={}
        )
    cow_docs = set(engine_cow.state.data["domain"]["documents"].keys())

    # --- Run 2: Proxy ---
    engine_proxy = _make_engine()
    engine_proxy.register(save_document_proxy)
    for i in range(N):
        await engine_proxy.execute(
            "save_document_proxy", doc_id=f"CMP-{i:03d}", metadata={}
        )
    proxy_docs = set(engine_proxy.state.data["domain"]["documents"].keys())

    expected = {f"CMP-{i:03d}" for i in range(N)}

    print(f"\n[Comparative] CoW result:   {sorted(cow_docs)} ({len(cow_docs)}/{N})")
    print(f"[Comparative] Proxy result: {sorted(proxy_docs)} ({len(proxy_docs)}/{N})")
    print(f"[Comparative] Expected:     {sorted(expected)}")

    cow_missing = expected - cow_docs
    proxy_missing = expected - proxy_docs

    if cow_missing and not proxy_missing:
        print(
            f"[Comparative VERDICT] BUG CONFIRMED:\n"
            f"  CoW loses: {sorted(cow_missing)}\n"
            f"  Proxy preserves all {N} documents.\n"
            f"  Root cause is in the return/merge mechanism, not infrastructure."
        )
        # Proxy phải đúng — assert này luôn phải pass
        assert proxy_docs == expected, "Proxy Mutation must save all documents"
        # Đây là "expected failure" của CoW — chỉ warn, không pytest.fail
        # vì mục đích test này là DOCUMENTATION, không chặn CI
        pytest.xfail(
            f"CoW data loss confirmed (INC-021): missing {sorted(cow_missing)}. "
            f"This is the known bug. Use Proxy Mutation instead."
        )
    elif not cow_missing and not proxy_missing:
        print("[Comparative VERDICT] Both patterns work — bug may be FIXED or NOT PRESENT in this version.")
        assert cow_docs == expected
        assert proxy_docs == expected
    else:
        # Proxy cũng bị mất → vấn đề ở tầng sâu hơn
        assert proxy_docs == expected, (
            f"[Comparative CRITICAL] Proxy Mutation also loses documents: {sorted(proxy_missing)}. "
            f"Root cause is deeper than return pattern."
        )


# ═══════════════════════════════════════════════════════════════════════════
# NHÓM 7: Regression guard — đảm bảo fix không bị revert
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_regression_proxy_mutation_never_loses_data():
    """
    Regression Guard: Proxy Mutation pattern PHẢI luôn tích lũy đúng.
    Test này phải LUÔN PASS — bất kể CoW có bị bug hay không.
    Nếu test này fail → có regression nghiêm trọng trong engine.
    """
    engine = _make_engine()
    engine.register(save_document_proxy)

    N = 10  # Nhiều hơn INC-021 để tăng confidence
    for i in range(N):
        await engine.execute(
            "save_document_proxy",
            doc_id=f"REG-{i:04d}",
            metadata={"seq": i},
        )

    final = dict(engine.state.data["domain"]["documents"])
    assert len(final) == N, (
        f"REGRESSION: Expected {N} documents, got {len(final)}. "
        f"Missing: {[f'REG-{i:04d}' for i in range(N) if f'REG-{i:04d}' not in final]}"
    )

    # Verify data integrity — không chỉ key, mà cả value
    for i in range(N):
        key = f"REG-{i:04d}"
        assert key in final, f"REGRESSION: {key} missing"
        assert final[key]["metadata"]["seq"] == i, f"REGRESSION: {key} data corrupted"

    print(f"[Regression] ✅ All {N} documents saved with correct data.")
