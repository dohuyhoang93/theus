---
id: INC-001
title: "Transaction Snapshot Lag Causes Sequential Document Loss"
area: core
severity: high
status: resolved
created: 2026-04-03T08:41:00+07:00
resolved: 2026-04-03T08:49:00+07:00
author: "Antigravity / Do Huy Hoang"
---

# INC-001: Transaction Snapshot Lag Causes Sequential Document Loss

## 1. Summary

Khi gọi `engine.execute("save_document", ...)` liên tiếp nhiều lần (>2), các document từ lần thứ 3 trở đi **bị mất khỏi state** dù Transaction commit thành công (version tăng đều). Nguyên nhân gốc: Transaction snapshot isolation trong Theus v3.0.25 đọc state **chậm 1 version**, khiến CoW (Copy-on-Write) return pattern clone một bản thiếu entry và ghi đè state.

## 2. Background

Hệ thống THEMA Document Management sử dụng Theus Engine v3.0.25 làm lớp nghiệp vụ. Process `save_document` ban đầu được thiết kế theo pattern **CoW (Copy-on-Write)**:

```python
# Pattern cũ — CoW
new_docs = dict(ctx.domain.documents)  # Clone snapshot
new_docs[doc_id] = {...}               # Thêm entry mới
return new_docs, new_queue             # Engine commit
```

Integration test `test_multiple_saves_accumulate` phát hiện: sau 5 lần save liên tiếp, state chỉ chứa **2 documents** thay vì 5.
---
id: INC-021-CORE
title: "Transaction Snapshot Lag and Explicit/Proxy Merge Precedence"
area: core
severity: high
status: resolved
resolution_type: structural+contract
created: 2026-04-03T08:41:00+07:00
resolved: 2026-05-02T00:00:00+07:00
author: "Antigravity / Do Huy Hoang"
---

# INC-021-CORE: Transaction Snapshot Lag and Explicit/Proxy Merge Precedence

## 1. Summary

Sequential executes could lose data when process code used Copy-on-Write return patterns under stale snapshot conditions.

The incident is now resolved with a structural core fix and contract hardening:

1. Rust commit precedence now ensures explicit pending updates win over overlapping inferred shadow deltas.
2. Python StateUpdate unwrapping was fixed to prevent transaction reference contamination.
3. Multi-output return contract is now strict: scalar return for multi-output is a contract violation.

## 2. Original Symptoms

Observed behavior in sequential saves:

1. Engine version increased normally.
2. Later writes could silently drop prior entries.
3. Failure surfaced most clearly with CoW processes returning full dict/list structures.

This manifested as deterministic data loss after repeated calls in the same engine instance.

## 3. Root Cause (Final)

### 3.1 Forensic observation

Context read paths could behave like stale snapshots during rapid sequential execution.

### 3.2 Structural mechanism

The critical bug was precedence during commit merge:

1. Inferred shadow deltas (from proxy/CoW tracking) were replayed.
2. Explicit pending updates (from output mapping or tx.update) were also present.
3. Overlapping stale shadow deltas could overwrite explicit updates in some paths.

Result: silent loss of newly written values.

## 4. Resolution Implemented

### 4.1 Rust core fix (commit precedence)

In [src/engine.rs](src/engine.rs):

1. Collect explicit pending paths from nested pending data.
2. Normalize path notation for robust overlap checks.
3. Skip inferred shadow delta replay when the delta path overlaps an explicit pending path.

Policy now enforced at commit time: explicit pending updates take precedence over inferred deltas.

### 4.2 Python fix (StateUpdate deep unwrap)

In [theus/engine.py](theus/engine.py):

1. Deep unwrap now includes payloads inside StateUpdate objects.
2. Prevents leaking transaction-bound wrappers into committed state.
3. Removes a class of deepcopy/isolation failures on subsequent transactions.

### 4.3 Contract hardening (multi-output strictness)

In [theus/contracts.py](theus/contracts.py):

For process declarations with multiple outputs, scalar return values are now rejected.

Allowed multi-output return forms:

1. `None` (proxy-only write path)
2. tuple/list (positional explicit values)
3. dict (key-mapped explicit values)

Invalid form:

1. scalar non-None return (for example `"ok"`) -> ContractViolationError

## 5. Current Contract Policy

### 5.1 Recommended default

1. Explicit output return is default for most business processes.
2. Proxy mutation remains supported and valid.

### 5.2 When proxy is used

1. Multi-output proxy-only processes must return `None`.
2. Do not rely on scalar ack returns for multi-output.
3. Avoid mixing proxy and explicit writes to the same path in one process unless intentionally tested.

## 6. Verification Evidence

Validation completed in this repository state:

1. Full test suite: `381 passed, 4 skipped, 0 failed`.
2. Incident regression suite: [tests/11_rfc001/test_inc021_snapshot_lag.py](tests/11_rfc001/test_inc021_snapshot_lag.py) passing.
3. Explicit stress suite: [tests/test_explicit_contract_stress_4case.py](tests/test_explicit_contract_stress_4case.py) passing.
4. Proxy stress suite: [tests/test_proxy_mutation_stress_4case.py](tests/test_proxy_mutation_stress_4case.py) passing.

## 7. Impact and Residual Risk

### 7.1 Incident impact (historical)

1. Silent data integrity risk under repeated writes.
2. Affected process styles using full-state CoW returns under stale read conditions.

### 7.2 Residual risk (current)

1. Mixing proxy and explicit writes in the same logical field set can still reduce clarity for maintainers.
2. Single-output scalar returns remain valid by design; teams should keep this intentional and documented.

## 8. Preventive Actions

1. Keep explicit-first coding guidance for new processes.
2. Require multi-output processes to be explicit about return shape (`None`, tuple/list, or dict).
3. Retain stress tests for both explicit and proxy patterns.
4. Add lint guidance for multi-output scalar returns where practical.

## 9. Related Files

1. [src/engine.rs](src/engine.rs)
2. [theus/engine.py](theus/engine.py)
3. [theus/contracts.py](theus/contracts.py)
4. [tests/11_rfc001/test_inc021_snapshot_lag.py](tests/11_rfc001/test_inc021_snapshot_lag.py)
5. [tests/test_explicit_contract_stress_4case.py](tests/test_explicit_contract_stress_4case.py)
6. [tests/test_proxy_mutation_stress_4case.py](tests/test_proxy_mutation_stress_4case.py)

## 10. Timeline (Condensed)

1. 2026-04-03: Incident observed and reproduced with deterministic sequential data loss.
2. 2026-04-03: Immediate mitigation applied in application code (proxy-oriented workaround).
3. 2026-05-02: Structural fix in core merge precedence and contract hardening completed.
4. 2026-05-02: Full repository validation completed with no failing tests.

| **Actor 2** | `Transaction.__init__` — deepcopy state for snapshot isolation |
| **Actor 3** | `_attempt_execute` — maps return values to `pending_data`, calls `tx.update()` |
| **Actor 4** | Rust Core `compare_and_swap` — atomic state update |
| **Outside** | Application code (test, API) — chỉ gọi `engine.execute()` |

#### Phase 2: Dynamic Analysis

**Reinforcing Loop R1 — "Snapshot Drift":**
```
Execute(N) commits → State version +1
       ↓
Execute(N+1) creates Transaction → deepcopy state at version N (ok)
       ↓
But ContextGuard wrapping reads version N-1 (lag!)
       ↓
Process clones stale data → returns dict missing Execute(N)'s entry
       ↓
CAS commit overwrites → Execute(N)'s entry lost
       ↓
Loop repeats: each execute loses the previous one's data
```

**Balancing Loop B1 — "Proxy Mutation Bypass":**
```
Process writes directly to ContextGuard (proxy mutation)
       ↓
ContextGuard tracks delta in Transaction's pending writes
       ↓
CAS commit merges ONLY the delta (not full state replacement)
       ↓
No dependency on snapshot accuracy → data preserved
```

**Delay:** Khoảng 1 version giữa `_sync_registry_from_core()` và lần đọc tiếp theo của `Transaction.__init__`. Delay này **invisible** — không có error, không có warning.

#### Phase 3: Structural Excavation

| Level | Observation |
|---|---|
| **Event** | `BATCH-002` missing from state after 5 sequential saves |
| **Pattern** | Documents luôn bị mất bắt đầu từ lần execute thứ 3 trở đi, lặp lại 100% |
| **Structure** | Theus v3.1.5 "Smart CAS Optimization" thiết kế cho concurrent access (nhiều process cùng lúc), **không tối ưu cho sequential access** (cùng process lặp lại nhanh). Snapshot creation timing không đảm bảo read-after-write consistency. |

**Architectural Decision gây ra bug:** Quyết định dùng `pending_data[root] = {}` ("empty dict to trigger Rust Deep Merge") trong v3.1.5 tạo ra semantic ambiguity: khi process return full state, Engine không phân biệt được "đây là full replacement" vs "đây là partial merge". Kết quả phụ thuộc vào timing — chính xác là定义 của Heisenbug.

#### Phase 4: Leverage & Simulation

**Pivot Point:** Chuyển `save_document` (và mọi process tương tự) sang Proxy Mutation pattern.

**2nd-Order Effect Check:**
- ✅ `test_save_document_mutates_state` — PASS (proxy mutation ghi đúng)
- ✅ `test_outbox_populated_after_save` — PASS (append qua proxy)
- ✅ `test_multiple_saves_accumulate` — PASS (tích lũy đúng 5/5)
- ✅ `test_full_api_upload_verifies_engine_state` — PASS (E2E HTTP → Engine → State)
- ✅ `test_save_document_contract` (unit) — PASS (sau cập nhật test)
- ⚠️ Cần xác nhận: process return `None` khi dùng Proxy Mutation → Engine skip output mapping (code path `if val is None: continue` đã tồn tại trong `_attempt_execute`) → AN TOÀN.

## 5. Impact

| Dimension | Assessment |
|---|---|
| **Severity** | **HIGH** — Silent data loss. Không có error/exception. Test PASS giả (3/4 tests passed trước đó). |
| **Blast Radius** | Mọi process dùng CoW return pattern với sequential execution >2 lần |
| **Data Integrity** | Documents bị mất từ Theus state. Nếu sync_worker đã flush outbox trước khi state bị ghi đè → PostgreSQL có data nhưng Theus state thiếu → **desync giữa Engine và DB** |
| **Detectability** | RẤT THẤP — Bug chỉ manifest khi >2 sequential executes cùng process. Single execute luôn đúng. |

## 6. Resolution

### 6.1 Immediate Fix (Band-aid) — ĐÃ ÁP DỤNG

Chuyển `save_document.py` từ CoW return sang Proxy Mutation:

```diff
 def save_document(
     ctx: Any, doc_id: str, metadata: dict[str, Any], file_path: str
-) -> tuple[dict[str, Any], list[dict[str, Any]]]:
-    new_docs: dict[str, Any] = dict(ctx.domain.documents)
-    new_docs[doc_id] = {
+) -> None:
+    ctx.domain.documents[doc_id] = {
         "metadata": metadata,
         "file_path": file_path,
         "status": "active",
         "timestamp": time.time(),
     }
-    new_queue: list[dict[str, Any]] = list(ctx.domain.outbox_queue)
-    new_queue.append(msg)
-    return new_docs, new_queue
+    ctx.domain.outbox_queue.append(msg)
```

### 6.2 Structural Fix (Cure) — KHUYẾN NGHỊ

Báo cáo bug snapshot lag cho Theus Core team (chính là tác giả). Transaction snapshot cần đảm bảo **read-after-write consistency** cho sequential execution trong cùng engine instance. Cụ thể:
- `Transaction.__init__` nên đọc state tại version **sau** `_sync_registry_from_core()` hoàn tất
- Hoặc: ContextGuard nên đọc trực tiếp từ core state thay vì snapshot

### 6.3 Process Fix (Vaccine)

1. **Coding Standard mới:** Tất cả THEMA processes PHẢI dùng Proxy Mutation pattern, KHÔNG dùng CoW return cho mutable state.
2. **Test coverage:** `test_multiple_saves_accumulate` đã tồn tại và catch bug này — giữ nguyên.
3. **Documentation:** Thêm ghi chú vào `save_document.py` giải thích WHY dùng Proxy Mutation.

## 7. Preventive Actions

- [x] Test `test_multiple_saves_accumulate` đã catch đúng bug
- [x] Unit test `test_save_document_contract` đã cập nhật theo pattern mới
- [x] Comment `NOTE:` trong `save_document.py` giải thích lý do kiến trúc
- [ ] Audit tất cả processes khác (query_documents, update_version, sync_worker) để đảm bảo không dùng CoW return
- [ ] Tạo ADR cho quyết định "Proxy Mutation over CoW Return"
- [ ] Fix Theus Core snapshot lag (upstream)

## 8. Related

| Document | Link |
|---|---|
| ADR-Architecture | [ADR-Architecture.md](file:///c:/Users/dohoang/projects/THEMA/ADR-Architecture.md) |
| SOP Task Tracking | [SOP_Task_Tracking.md](file:///c:/Users/dohoang/projects/THEMA/SOP_Task_Tracking.md) |
| save_document.py (fixed) | [save_document.py](file:///c:/Users/dohoang/projects/THEMA/src/core/processes/save_document.py) |
| test_theus_engine.py | [test_theus_engine.py](file:///c:/Users/dohoang/projects/THEMA/tests/integration/test_theus_engine.py) |
| Pending: ADR-005 | Proxy Mutation over CoW Return (chưa tạo) |

## 9. Timeline

| Thời điểm | Sự kiện |
|---|---|
| 2026-04-03 08:41 | User báo cáo lỗi integration test liên quan Theus CAS |
| 2026-04-03 08:42 | Chạy test suite → xác định `test_multiple_saves_accumulate` FAILED |
| 2026-04-03 08:43 | Phân tích error: `SupervisorProxy cap=0001`, không có CAS conflict |
| 2026-04-03 08:45 | Debug script v1: xác nhận raw core docs bị giữ ở 2 entries |
| 2026-04-03 08:47 | Debug script v3: trace bên trong process — phát hiện `dict(ctx.domain.documents)` chậm 1 version |
| 2026-04-03 08:48 | Root cause xác định: Transaction snapshot lag |
| 2026-04-03 08:48 | Fix: chuyển save_document sang Proxy Mutation pattern |
| 2026-04-03 08:49 | Verify: 13/13 tests PASSED, Mypy PASS, Ruff PASS (src/) |
| 2026-04-03 08:52 | Phát hành INC-001 chính thức |

## 10. Comprehensive Analysis & Resolution Plan

### 10.1 Ethical & Epistemic Audit

| Filter | Assessment |
|---|---|
| **Humility** | Mức độ chắc chắn: **CAO** (deterministic repro 100%). Tuy nhiên, chưa đọc được source code Rust của Transaction — phân tích dựa trên behavioral observation. Có thể root cause ở Rust side khác với giả thuyết về timing. |
| **Courage** | Fix hiện tại (Proxy Mutation) là **workaround đúng đắn**, nhưng structural fix thực sự cần sửa Theus Core. Không trốn tránh: đã ghi rõ trong Section 6.2 rằng upstream fix cần thiết. |
| **Integrity** | Không áp dụng double standard: cùng một CoW pattern có thể hoạt động đúng với 1-2 executes nhưng fail ở 3+. Chúng ta không "chấp nhận" bug chỉ vì most common use case (single execute) không bị ảnh hưởng. |
| **Justice** | Blame: **Không đổ lỗi cho developer** (CoW pattern là hợp lý theo lý thuyết) và **không đổ lỗi cho Theus Core** (snapshot isolation là trade-off thiết kế hợp lệ). Lỗi nằm ở **documentation gap** — Theus không document rõ snapshot timing behavior. |

### 10.2 Decision: Tại sao KHÔNG sửa Theus Core ngay?

1. Theus Core là Rust binary — sửa đòi hỏi rebuild toàn bộ PyO3 binding.
2. Proxy Mutation pattern **tốt hơn CoW** ngay cả khi snapshot đúng: ít allocation, ít deep copy, Engine chỉ merge delta.
3. Fix ở application level cho phép tiếp tục phát triển THEMA mà không block trên upstream.

### 10.3 Residual Risk

- **Outbox silent loss**: Outbox queue cũng dùng CoW clone trước đây. Đã fix sang `ctx.domain.outbox_queue.append()`. Tuy nhiên cần audit xem sync_worker có đọc outbox bằng CoW pattern không.
- **Other processes**: `query_documents.py` (read-only, không trả mutable state) → AN TOÀN. `update_version.py` → CẦN KIỂM TRA.
