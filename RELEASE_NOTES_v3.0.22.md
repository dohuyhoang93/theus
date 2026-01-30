# Release Notes v3.0.22 (Comprehensive Stabilization)

**Date**: 2026-01-31
**Criticality**: CRITICAL (Resolves Concurrent Data Corruption & Core Misalignment)

## 🚀 Overview
Version 3.0.22 marks the completion of the "Theus Stabilization Phase". It transforms Theus from a beta architecture into a production-hardened **Process-Oriented Operating System**. This release focuses on "Zero-Trust" integrity, resolving silent data loss, and synchronizing the entire documentation ecosystem (Tutorials, AI Guides, and Specs).

---

## 🛡️ Core Data Integrity & Safety

### 1. Silent Loss Prevention (Differential Shadow Merging)
- **Problem**: Sequential processes within a workflow could silently overwrite each other's changes if they touched nested fields not properly tracked by the old `DeepMerge` logic.
- **Solution**: Implemented **Differential Shadow Merging**. The engine now compares process output against a transaction-local "Shadow Cache" to precisely identify deltas, preventing unintended overwrites.
- **Fixed**: Silent Overwrite Bug in nested `dict`/`list` structures.

### 2. Zero-Trust Architecture (Delta Replay & Schema Gatekeeper)
- **Delta Replay**: The Rust Core now atomicaly replays deltas onto the global state, ensuring that only declared changes are committed.
- **Schema Gatekeeper**: Integrated Pydantic-style schema validation into the CAS (Compare-And-Swap) pipeline. Commits that violate the system schema are now blocked at the Rust boundary.

### 3. Concurrency & Performance Fixes
- **Double CAS Hang**: Fixed a deadlock in `test_concurrency_cas.py` where high-contention retry loops could enter a permanent hang.
- **TrackedList Migration**: Moved `TrackedList` logic from Python to Rust (`src/proxy.rs`) to eliminate synchronization lag and improve FFI performance.

---

## 🛠️ Developer Experience (DX) & Interoperability

### 1. SupervisorProxy & Interoperability
- **Transactional Mutations**: `SupervisorProxy` (Rust-backed) now supports standard Python mutation methods (`.append()`, `.pop()`, `.extend()`, `.update()`). These operations are intercepted by the proxy and tracked as deltas, ensuring full transaction safety and rollback capabilities.
- **Pydantic v2 Support**: Fully compatible with Pydantic v2. The engine now uses `model_validate` and `model_dump` for schema enforcement. Scaffolding includes `ConfigDict` patterns for seamless integration with Theus proxies.
- **TheusEncoder**: Added a specialized JSON encoder in `theus.interop` for handling SHM-backed tensors and tracked proxies during `json.dumps()`.

### 2. Async Execution Engine
- **Async `engine.execute`**: Transitioned the main execution method to `async def`. This enables non-blocking conflict resolution using `asyncio.sleep()`, preventing thread starvation during high-contention CAS retries.
- **Sync-to-Async Bridge**: Introduced `_run_process_sync` to safely bridge synchronous callers (like the Rust core or `execute_workflow`) to the asynchronous engine, preventing deadlocks.
- **Usage**: Workflow triggers (`engine.execute_workflow`) remain synchronous entry points for CLI/Scripts, while direct process calls require `await`.

---

## 📚 Documentation Synchronization (Mass Update)

We have performed a global audit and sync of the **entire documentation directory** (~40+ files):

- **Naming Convention**: Standardized `domain_ctx` -> `domain` across all tutorials and specs to match the v3.0.22 core.
- **AI Tutorials (10 Modules)**: Fully updated for v3.0.22, including modernized worker patterns (Asyncio instead of threading) and GPU/Tensor management.
- **English Tutorials (23 Chapters)**: Synchronized with the latest mutation advice and transaction rollback patterns.
- **Architecture Heritage**: Added clear markers to legacy ADRs and RFCs to distinguish design history from active API documentation.
- **Interactive Map**: Overhauled `00_Start_Here_Map.md` with persona-based navigation (Implementer, AI, Architect).

---

## 🔧 Installation & Upgrade
```bash
# Upgrade to the stabilized core
pip install theus==3.0.22 --upgrade
```

**Maintained by**: Do Huy Hoang & Theus Core Team
