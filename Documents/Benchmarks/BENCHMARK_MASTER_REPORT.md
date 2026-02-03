# Theus Framework Benchmark Master Report
**Date:** 2026-02-02
**Version:** v3.0.22 (Zero Trust + Zero Copy)
**Environment:** Windows | Python 3.14.2 (Free-Threading) | Rust Core v3.1.2

---

## 1. Executive Summary

This report validates the performance characteristics of Theus v3.0.22. The architecture prioritizes **Safety** (Deep Guard) and **Scalability** (Zero-Copy) over raw micro-latency.

**Key Findings:**
1.  **Zero-Copy is Mandatory for Scale:** In 200MB stress tests, Theus Zero-Copy is **3x faster** and uses **~N times less RAM** than standard Multiprocessing.
2.  **Sub-Interpreters are the Future:** Initialization of isolated contexts is **12.7x faster** using Sub-interpreters compared to Process Spawning.
3.  **Safety Costs:** The "Zero Trust" Deep Guard introduces a ~50x overhead on micro-reads (10µs vs 0.2µs). This is an intentional design choice to guarantee Transaction Isolation.

---

## 2. Core Performance (Micro-Benchmarks)

### 2.1 Proxy Overhead (Read/Write)
Measures the cost of the `SupervisorProxy` which enforces permissions and transaction logs.

| Mechanism | Latency / Op | Relative to Native | Evaluation |
| :--- | :--- | :--- | :--- |
| **Native Python** | 0.19 µs | 1x | Baseline |
| **Theus Proxy** | **9.59 µs** | ~50x | Acceptable for control logic (not suitable for tight loops). |

### 2.2 Serialization (TheusEncoder)
Measures the speed of converting the State to JSON for API responses.

| Method | Time (5k items) | Speedup |
| :--- | :--- | :--- |
| Legacy `dict()` cast | 7.12 ms | 1x |
| **TheusEncoder** | **2.05 ms** | **3.5x** 🚀 |

---

## 3. High-Performance Computing (Heavy Zone)

### 3.1 Zero-Copy Vector Ops
Measures execution time for Matrix Multiplication (3000 x 3000 float64).

| implementation | Execution Time | vs. Pickle (Standard) | Notes |
| :--- | :--- | :--- | :--- |
| MP Pickle | 3.12 s | 1x | Baseline (High RAM usage). |
| **Theus Core ZC** | **2.87 s** | **1.09x** | Efficient, no memory copy. |
| **Theus Engine API** | 4.50 s | 0.69x | API Overhead (Process Pool wrapper). |

### 3.2 Scalability (200MB Stress Test)
Stress test with 200MB Payload (5000 x 5000) to demonstrate "Wall" effects.

| Mechanism | Time | RAM Impact |
| :--- | :--- | :--- |
| ProcessPool (Pickle) | 1.71 s | **O(N)** (Copy per worker). Risk of OOM. |
| **Theus Zero-Copy** | **0.56 s** | **O(1)** (Shared). Constant RAM usage. |
| **Speedup** | **3.0x** | Essential for AI Workloads. |

---

## 4. Isolation Technology (Experimental)

Comparison between classic ProcessPool and PEP 684 Sub-Interpreters (Python 3.14).
*Note: Sub-interpreters running in Pure Python Fallback mode (NumPy limitation).*

| Metric | ProcessPool (Spawn) | Sub-Interpreters | Speedup |
| :--- | :--- | :--- | :--- |
| **Initialization** | 1.50 s | **0.11 s** | **12.7x** 🚀 |
| **Execution** | 1.20 s | 0.71 s | 1.7x |

**Conclusion:** Sub-interpreters drastically reduce "Cold Start" latency, making them ideal for high-frequency agent ticks.

---

## 5. Deployment Recommendations

1.  **Use `ctx.heavy` for Everything > 10KB:** The overhead of the Proxy (50x) makes it unsuitable for arrays. Use Heavy Zone (Zero-Copy) for all data payloads.
2.  **Enable `TheusEncoder`:** For all REST APIs, use the optimized encoder to reduce serialization lag by 70%.
3.  **ProcessPool for Now:** Until NumPy supports PEP 684 fully, stick to `THEUS_USE_PROCESSES=1`. Theus is "Sub-Interpreter Ready" and will provide free speedups when the ecosystem catches up.

---
*Report generated purely from `benchmarks/` execution logs.*
