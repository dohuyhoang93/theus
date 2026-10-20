# Theus v2.2.0 Release Notes

**"The Iron Core" Update**

Theus v2.2.0 marks a monumental shift from a Hybrid-Python architecture to a **Rust-First Microkernel**. This release focuses on Type Safety, Security Hardening, and Massive Scalability for AI workloads.

## 🚀 Key Highlights

### 1. Rust-First Kernel (`theus_core`)
The entire Transaction Engine, Context Guards, and Process Registry have been rewritten in Rust.
-   **Threads:** True Thread-Safety with Rust `RwLock`.
-   **Performance:** 10x reduction in overhead for deep state access.
-   **Correctness:** Impossible to have "leaking guards" due to Rust's ownership model.

### 2. Strict Mode (Security)
By default in `theus init` projects, the engine now runs in `strict_mode=True`.
-   **No Private Access:** Reading `_attr` is `PermissionDenied`.
-   **Control Plane Guard:** `inputs=['SIG']` or `inputs=['CMD']` is forbidden.
-   **Immutable Inputs:** Input data is presented as `FrozenDict` / `FrozenList`.

### 3. Native Finite State Machine (FSM)
Orchestration logic is now powered by a Rust FSM.
-   **Determinism:** State transitions are atomic.
-   **Resilience:** Automatic rollback on chain failure.

### 4. Heavy Zone Optimization (New)
Introduced `HEAVY` Zone for AI Tensors and Binary Blobs.
-   **Prefix:** `heavy_` (e.g., `heavy_tensor`).
-   **Behavior:** Bypasses Transaction Log (Zero-Copy) but maintains Audit.
-   **Trade-off:** Changes to Heavy data are **NOT** reverted on Rollback (Performance > Consistency for Blobs).

### 5. Build System
-   Migrated to `maturin` (PEP 621 Standard).
-   Unified `pyproject.toml`.
-   Cross-platform wheels (windows/linux/macos).

## ⚠️ Breaking Changes
-   **Chapter 11 Update:** `WorkflowManager` API has evolved. See updated docs.
-   **Legacy Scripts:** `setup.py` and old verification scripts (`verify_*.py`) have been removed.

## 📦 Installation
```bash
pip install theus
# Or for dev:
maturin develop
```
