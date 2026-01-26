# Release Notes - Theus Framework v3.0.1 (Codename: E-Motion)

**Release Date:** 2026-01-17
**Stability:** Stable Production Release
**Python Support:** 3.12, 3.13, 3.14 (Experimental)

## 🚀 Major Highlights

### 1. Reliable Outbox Integrations (Rust-Powered)
The Outbox Pattern has been completely re-architected down to the Rust Core (`theus_core`), providing absolute reliability for distributed systems.
*   **Atomic Commit Guarantee:** Outbox messages (`ctx.outbox.add`) are now tightly bound to the Transaction lifecycle. If a Process fails or rolls back, Outbox messages are **automatically discarded**, ensuring no phantom messages are ever sent when system state hasn't actually changed.
*   **Zero-Overhead:** Message queuing happens directly within Rust data structures, avoiding Python serialization costs.

### 2. True Parallelism (Experimental Support)
Experimental support for **PEP 554 (Multiple Interpreters)** on Python 3.14.
*   **Interpreter Pool:** Centralized management of isolated Sub-interpreters.
*   **Pure Task Support:** Supports CPU-bound tasks via **Deep Copy (Pickle)**.
*   **Roadmap:** v3.1 will introduce **Zero-Copy Shared Memory** (`ctx.heavy`) for high-performance AI workloads.
*   **Known Limitation:** Direct sharing of Rust Core objects (`State`) is not supported; data is marshalled across boundaries.

### 3. Codebase Modernization (PEP 489)
All Rust source code (`src/*.rs`) has been standardized to support **Multi-Phase Initialization**.
*   All PyO3 Classes (`TheusEngine`, `AuditSystem`, etc.) are now tagged with `#[pyclass(module="theus_core")]`.
*   Improved compatibility with embedded Python environments and module reloading.

---

## 🛠 Improvements & Fixes

*   **Audit System Enforcement:** Fixed and tested the **Audit Block** feature. The system now actively locks Processes (raises `AuditBlockError`) when error thresholds are exceeded, rather than just passively logging.
*   **Workflow Engine:** Separated Workflow execution (Sync) from the main AsyncIO Loop, preventing Deadlock conditions when running complex scenarios.
*   **Path Resolution:** Improved automatic configuration file discovery (`specs/`, `workflows/`) based on execution location, fixing `FileNotFoundError` when running from different directories.

## 📦 Upgrade Instructions

```bash
pip install theus==3.0.1
```

## ✅ Verification Status
The `theus_integration_test` suite passed 100% on Windows/Python 3.13 & 3.14.

| Feature | Status |
| :--- | :--- |
| Core Transaction | ✅ Stable |
| Flux DSL | ✅ Stable |
| Audit Guards | ✅ Stable |
| Outbox Pattern | ✅ Stable |
| Parallelism | ⚠️ Experimental (Pure Only) |
