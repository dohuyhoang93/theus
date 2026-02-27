# Theus Framework v3.0.22 — Benchmark Report

> **Date:** 2026-02-27 09:12 UTC+7
> **System:** Windows, CPython 3.14, Rust (release profile)
> **Hardware:** Local dev machine

---

## Summary

| Benchmark | Key Metric | Result |
|-----------|-----------|--------|
| Isolation (InterpreterPool vs ProcessPool) | Init Speedup | **6.17x** |
| SignalHub Throughput | recv() throughput | **169,722 msgs/s** |
| Zero-Copy Matrix (3000×3000, 68MB) | Sequential baseline | 1.71s |
| Comprehensive — Read Proxy | Overhead | 75.7x |
| Comprehensive — Deep Merge | Write Duration | 1.29 ms ✅ |
| Comprehensive — Heavy Zone | Efficiency | **1.20x** (near-ideal) |
| Comprehensive — TheusEncoder | vs dict() cast | **5.3x faster** |
| Scalability (200MB matrix) | ZC vs Pickle | **2.06x faster** |
| Read Performance — Shallow | SupervisorProxy | 3,589,938 ops/s (0.95x) |
| Read Performance — Deep | SupervisorProxy | 132,648 ops/s (0.56x) |

---

## 1. Isolation Benchmark (`benchmark_isolation.py`)

So sánh `InterpreterPool` (PEP 684) vs `ProcessPool` (Spawn).

| Metric | ProcessPool | InterpreterPool | Speedup |
|--------|-------------|-----------------|---------|
| Init Time | 1.2239s | 0.1983s | **6.17x** |
| Exec Time (4 workers) | 0.7148s | 0.8469s | 0.84x |

> **Nhận xét:** InterpreterPool init nhanh gấp 6x nhờ tránh fork overhead. Exec time tương đương.

---

## 2. SignalHub Performance (`benchmark_signalhub.py`)

| API | Throughput | Latency |
|-----|-----------|---------|
| `recv()` blocking | **169,722 msgs/s** | 5.89 μs |
| `recv_async()` native | 6,150 msgs/s | 162.59 μs |
| `asyncio.to_thread(recv())` | 4,185 msgs/s | 238.96 μs |

> **Nhận xét:** `recv()` blocking có throughput cao nhất. `recv_async()` overhead +2659% do asyncio event loop. `recv_async()` nhanh hơn `to_thread()` 1.5x.
>
> ⚠️ `recv_async()` overhead cao — cân nhắc dùng `recv()` trong thread cho latency-critical paths.

---

## 3. Zero-Copy Matrix Benchmark (`benchmark_zero_copy.py`)

Ma trận 3000×3000 float64 (68.66 MB), 4 workers.

| Method | Time | vs Sequential |
|--------|------|---------------|
| Sequential | 1.7074s | 1.00x |
| Multi-thread (GIL) | 1.8821s | 0.91x |
| ProcessPool (Pickle) | 3.9442s | 0.43x |
| Theus Core ZC | 3.7552s | 0.45x |
| Theus Engine API | 4.3005s | 0.40x |

> **Nhận xét:** GIL blocker trên CPU-bound tasks. Zero-Copy tránh pickle overhead nhưng engine routing thêm 0.55s. Scalability test (bên dưới) cho thấy ZC win rõ ràng ở dataset lớn hơn.

---

## 4. Comprehensive Benchmark (`comprehensive_benchmark.py`)

5000 items, 1000 ops, 1M floats array. **Strict Mode ON**.

### Case 1: Read Performance
```
Native Python: 0.18 us/op
Theus Proxy:   13.69 us/op
Overhead:      75.7x
```

### Case 2: Deep Merge Write (v3.1.2)
```
Write Duration: 1.29 ms
Integrity Check: ✅ PASSED (No silent overwrite)
```

### Case 3: Heavy Zone Zero-Copy
```
Native Numpy:   4.12 ms
Theus Heavy:    4.95 ms
Efficiency:     1.20x (Ideal ~1.0x)
```

### Case 4: Serialization
```
Manual dict() cast: 10.52 ms
TheusEncoder:       1.98 ms → 5.3x faster
```

### Case 5: Pydantic Interop
```
Interoperability Check: ✅ PASSED
```

> **Nhận xét:** Proxy read overhead 75x là expected (FFI + zone physics check mỗi access). Heavy Zone gần native (~1.2x) nhờ ShmArray zero-copy. TheusEncoder 5x nhanh hơn manual dict() cast.

---

## 5. Scalability Test (`scalability_test.py`)

Ma trận 5000×5000 float64 (**200MB**).

| Method | Time | RAM |
|--------|------|-----|
| Traditional Pickle | 1.0028s | High (copy per worker) |
| Theus Zero Copy | **0.4869s** | Near-Zero |

> **Speedup: 2.06x** — Zero-Copy bỏ qua hoàn toàn chi phí serialize/deserialize.

---

## 6. Read Performance (`test_read_performance.py`)

10,000 items in state.

### Shallow Access (single key)
| Method | ops/s | Ratio |
|--------|-------|-------|
| Legacy (FrozenDict) | 3,774,232 | 1.00x |
| Supervisor (Proxy) | 3,589,938 | **0.95x** |

### Deep Access (nested path)
| Method | ops/s | Ratio |
|--------|-------|-------|
| Legacy `['key']` | 235,338 | 1.00x |
| Supervisor `.attr` | 132,648 | **0.56x** |

> **Nhận xét:** Shallow reads gần như không overhead (0.95x). Deep access chậm hơn 44% do `__getattr__` chain resolution qua SupervisorProxy → ContextGuard → Rust guards.

---

## Key Takeaways

1. **Heavy Zone SHM** hoạt động near-native (1.2x) — đúng thiết kế zero-copy
2. **InterpreterPool** init nhanh 6x so với ProcessPool — sub-interpreter PEP 684 hiệu quả
3. **TheusEncoder** 5.3x nhanh hơn `dict()` cast — Rust accelerated serialization
4. **Proxy overhead** 75x cho read access — trade-off cho safety (zone physics, strict mode, contract checks)
5. **Zero-Copy** win 2x ở 200MB+ datasets — bỏ qua pickle serialization hoàn toàn
6. **SignalHub recv()** 170K msgs/s — đủ cho real-time pub/sub
