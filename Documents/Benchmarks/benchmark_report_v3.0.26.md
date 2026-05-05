# Theus v3.0.26 — CI / Benchmarks / Scaffold Audit Report
**Date:** 2026-05-05  
**Method:** Systems Thinking Engine + Intellectual Virtue Auditor  
**Scope:** Full pipeline — Rust core ↔ PyO3 FFI ↔ Python wrapper ↔ Workflow engine ↔ Scaffold

---

## Systems Analysis Summary

| Dimension | Finding |
|---|---|
| **Scope** | Theus v3.0.26 — toàn bộ pipeline |
| **Dynamics** | 2 reinforcing loops rủi ro + 1 balancing loop hoạt động tốt + 2 điểm delay cấu trúc |
| **Root Structure** | FFI crossing cost & async runtime translation là "thuế ẩn" trên mọi hot path |
| **Leverage Point** | `recv_async()` cần tái kiến trúc; Proxy read cần lazy-evaluation hoặc batching |

---

## I. CI Pipeline — Kết Quả

**Lệnh:** `.\.venv\Scripts\python.exe scripts/Local_CI.py verify`

| Step | Kết quả | Thời gian |
|---|---|---|
| Compiling Rust Core (Maturin) | ✅ SUCCESS | 10.02s |
| Cargo Clippy (Strict + Pedantic) | ✅ SUCCESS | 12.68s |
| Pyright | ✅ SUCCESS — 0 errors, 0 warnings | 3.85s |
| Ruff | ✅ SUCCESS | 0.97s |
| Rust Tests | ✅ SUCCESS — 1 passed | 26.35s |
| Verify API Parity | ✅ SUCCESS | 2.59s |

### Ghi chú: Parity Gaps chưa phân loại

6 methods bị đánh dấu `"Missing in Python Wrapper (Intentional?)"`:
- `commit_state`, `execute_process_async`, `report_conflict`
- `report_success`, `set_audit_system`, `set_strict_cas`, `set_strict_guards`

**Vấn đề:** CI không phân biệt được "abstraction có chủ đích" vs "bị quên". Cần thêm annotation `# INTENTIONALLY INTERNAL` trong `verify_api_parity.py` để loại bỏ false alarm vĩnh viễn.

---

## II. Benchmarks — Kết Quả Chi Tiết

### II.1 benchmark_isolation.py — Process vs Interpreter Pool

| Metric | ProcessPool | InterpreterPool | Speedup |
|---|---|---|---|
| Init time | 1.169s | 0.037s | **31.3x** ✅ |
| Exec time (4 workers) | 0.732s | 0.598s | 1.2x |

**Kết luận:** InterpreterPool (PEP 684) là lợi thế thực sự cho workload có nhiều process init. Exec speedup khiêm tốn (1.2x) — đây là kết quả bình thường vì GIL vẫn áp dụng cho Python code.

---

### II.2 benchmark_signalhub.py — SignalHub Throughput

| Mode | Throughput | Latency |
|---|---|---|
| `recv()` blocking | 160,901 msg/s | **6.2 μs** |
| `recv_async()` native | 6,399 msg/s | 156 μs |
| `asyncio.to_thread(recv())` | 3,859 msg/s | 259 μs |

**⚠️ Critical Finding:** `recv_async()` overhead **+2414%** so với blocking.

**Root Cause (Structural):** Python asyncio event loop và Tokio runtime (Rust) không chia sẻ thread pool. Mỗi `recv_async()` call phải bridge 2 event loops — đây là O(1) FFI overhead không thể optimize bằng batching.

**Recommendation:** Document rõ: *"Use blocking `recv()` in a dedicated thread (via `asyncio.to_thread`) for high-frequency signal polling. Reserve `recv_async()` for low-frequency, latency-tolerant use cases."*

---

### II.3 benchmark_zero_copy.py — 3000×3000 Matrix (68 MB)

| Mode | Time | vs Sequential |
|---|---|---|
| Sequential | 1.75s | 1.0x (baseline) |
| Multithread GIL | 2.22s | 0.79x |
| Multiprocess Pickle | 4.85s | 0.36x |
| **Theus Core ZC** | 3.32s | 0.53x |
| Theus Engine API | 5.78s | 0.30x |

**⚠️ Phát Hiện Quan Trọng:** Ở 68MB, Zero-Copy **chậm hơn** sequential 2x.

**Root Cause:** Overhead của SHM registration + worker spawning > lợi ích zero-copy ở data size nhỏ.

---

### II.4 scalability_test.py — 190 MB Matrix

| Mode | Time | So sánh |
|---|---|---|
| Pickle (traditional) | 1.09s | baseline |
| **Theus Zero Copy** | **0.52s** | **2.1x nhanh hơn** ✅ |

**Kết luận kết hợp II.3 + II.4:** Zero-copy có **ngưỡng hiệu quả ~100-150MB**. Dưới ngưỡng này, overhead > lợi ích. **Tài liệu hiện tại chưa nêu ngưỡng này** — cần bổ sung vào API Reference.

---

### II.5 comprehensive_benchmark.py

| Case | Kết quả | Đánh giá |
|---|---|---|
| Read: Native vs Proxy | **207x overhead** | ⚠️ Structural debt |
| Deep Merge Write | 1.45ms — Integrity ✅ | ✅ Bình thường |
| Heavy Zone vs Numpy | 4.72ms vs 3.81ms (1.24x) | ✅ Chấp nhận được |
| **TheusEncoder vs dict()** | **2.01ms vs 8.96ms — 4.5x** | ✅ Quick win lớn |
| Pydantic Interop | ✅ PASSED | ✅ |

**Proxy Read 207x Overhead — Phân tích:**  
Mỗi `ctx.field.subfield` = 1 FFI crossing qua PyO3 → snapshot fresh từ Rust state. Không có read cache tại tầng Python. Với workflow 10 process × 5 reads = **50 FFI roundtrip per transaction**.

**TheusEncoder — Quick Win chưa được khai thác:**  
4.5x nhanh hơn `dict()` cast nhưng chưa xuất hiện trong best practice bắt buộc. Cần đưa vào scaffold template và tutorial mặc định.

---

### II.6 test_read_performance.py — Proxy Read Overhead

| Mode | Throughput | Speedup |
|---|---|---|
| FrozenDict (legacy) | 3.81M ops/s | baseline |
| SupervisorProxy | 3.08M ops/s | 0.81x |
| Deep access legacy | 182K ops/s | baseline |
| **Deep access Proxy** | **112K ops/s** | **0.62x ⚠️** |

**Reinforcing Loop R1 được xác nhận:**
```
Nhiều process → Nhiều Proxy reads → Nhiều FFI crossings → 
Latency tăng → Developer workaround bằng dict() cast → 
Mất audit trail → Bugs khó debug → Nhiều process hơn để compensate
```

---

## III. Scaffold — Kết Quả

**Lệnh:** `.\.venv\Scripts\python.exe theus/scaffold/main.py {1|2|3}`

| Kịch bản | Kết quả | Ghi chú |
|---|---|---|
| 1. E-Commerce (Standard POP) | ✅ PASS | Order → Payment → Invoice đúng thứ tự |
| 2. Async Outbox (Signals & Jobs) | ✅ PASS | Signal inject → flux → async join ~4s |
| 3. Parallel Processing (SHM) | ✅ PASS | 10M floats, 4 workers, Consensus ✅ |

### Rủi ro cấu trúc trong Scaffold

**Kịch bản 2 — Orphaned Task Risk:**
```python
_TASK_REGISTRY = {}  # Ephemeral, không được engine quản lý
task = asyncio.create_task(heavy_async_job(2.0))
_TASK_REGISTRY[job_id] = task
```
Nếu engine bị restart/reload, task handle bị mất nhưng coroutine vẫn chạy. Engine không có cơ chế cancel orphaned tasks.

**Kịch bản 3 — Stale SHM trên Worker Crash:**
`engine.heavy.cleanup()` chỉ được gọi trong happy path. Nếu worker crash, shared memory segment tồn tại cho đến lần Registry GC tiếp theo (khi engine khởi động lại). File `.theus_memory_registry.jsonl` là bằng chứng — GC cleanup log xuất hiện mỗi lần khởi động.

---

## IV. Bản Đồ Rủi Ro Hệ Thống

```
Reinforcing Loop R1 — Proxy FFI Tax (Đang hoạt động):
  Nhiều process reads → Nhiều FFI crossings → Latency tăng tuyến tính
  → Developer bypass bằng dict() cast → Mất audit trail

Reinforcing Loop R2 — Async Degradation (Tiềm ẩn):
  recv_async() chậm → Developer dùng to_thread() → Thread pool saturation
  → Asyncio event loop degradation → Mọi async path bị ảnh hưởng

Balancing Loop B1 — SHM Registry GC (Hoạt động nhưng lazy):
  Stale SHM entries → GC cleanup khi engine khởi động
  [Gap: không real-time, crash window có thể leak resource]
```

---

## V. Leverage Points — Ưu Tiên

| Priority | Action | Impact |
|---|---|---|
| 🔴 Cao | `recv_async()` — deprecation notice hoặc rewrite bridge | Ngăn R2 loop |
| 🔴 Cao | Proxy read caching: snapshot once per transaction, không per-attribute | Phá R1 loop |
| 🟡 Trung | Document zero-copy threshold: "Use when data > ~100MB" | Tránh misuse |
| 🟡 Trung | Engine-managed task lifecycle cho Async Outbox pattern | Fix B1 gap |
| 🟢 Thấp | Phân loại 6 parity gaps: `# INTENTIONALLY INTERNAL` | Hygiene CI |
| 🟢 Thấp | Đưa TheusEncoder vào scaffold template mặc định | Quick win 4.5x |

---

## VI. Verdict

**Theus v3.0.26 có foundation kiến trúc tốt:**
- CI pipeline hoàn toàn sạch
- POP contracts rõ ràng và được enforce bởi Rust core
- Zero-copy ở large scale hoạt động đúng thiết kế
- Scaffold demos functional và đúng pattern

**Các vấn đề trên là performance debt và documentation gaps, không phải correctness bugs.** Hệ thống đang chạy đúng — chưa chạy tối ưu ở một số hot path cụ thể. Ưu tiên fix R1 (Proxy read caching) sẽ có impact lớn nhất với rủi ro thấp nhất.
