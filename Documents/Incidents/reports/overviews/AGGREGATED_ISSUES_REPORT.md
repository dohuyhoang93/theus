# AGGREGATED ISSUES REPORT: THEUS FRAMEWORK (V3 ADR Analysis)

**Date:** 2026-01-29
**Source:** `/Documents/ADR/V3` (13 Docs) + `/Documents/AUDIT_V3_0_2.md`
**Scope:** All versions mentioned (v3.0.x - v3.1.x)

This report consolidates all defects, vulnerabilities, false claims, and architectural gaps identified across the internal Architecture Decision Records.

---

## 1. 🔴 Critical Data Integrity & Logic Issues

### 1.1. The "Silent Overwrite" Bug (Resolved)
- **Status:** ✅ Fixed (v3.1.2)
- **Problem:** `tx.update(data=...)` performs a Deep Replacement instead of a Deep Merge.
- **Verification:** `tests/02_safety/repro_overwrite.py` PASS.
- **Fix:** Implemented `deep_update_inplace` in `structures_helper.rs` and updated `engine.rs` to use recursive merge.

### 1.2. Output Path Resolution Logic (Resolved)
- **Status:** ✅ Fixed (v3.1.2)
- **Problem:** `@process(outputs=['domain.order.orders'])` that returns a List will often overwrite the **parent object** (`domain.order`) instead of the leaf field.
- **Verification:** `tests/02_safety/repro_path_resolution.py` PASS.
- **Fix:** Enhanced `deep_update_inplace` to support dot-notation path expansion (`deep_update_at_path`).

### 1.3. Legacy Context Reference Leak (Fixed)
*   **Source:** `002_Context_Leak_Incident.md`, `AUDIT_V3_0_2.md`
*   **Description:** `ctx.domain_ctx` returned raw references to state, allowing mutation outside of Transaction control.
*   **Fix Verification:** `src/structures.rs` uses `SupervisorProxy`. `guards.rs` enforces Proxy wrapping.
*   **Status:** ✅ **VERIFIED FIXED** in v3.0.2.

### 1.4. Permission Error / Supervisor Fallback (Fixed)
*   **Source:** `V3_PostMortem_Permission_Error.md`
*   **Description:** `ContextGuard` failed to upgrade to "Write Mode" if `tx` object was missing, causing `PermissionError` on valid writes.
*   **Fix Verification:** `ContextGuard` implementation (`guards.rs`) correctly accepts injected `tx`.
*   **Status:** ✅ **VERIFIED FIXED** in v3.1.

### 1.5. Unsafe FrozenDict (Fixed)
*   **Source:** `ADR_Supervisor_Architecture_v3_1.md`
*   **Description:** Legacy `FrozenDict` allowed shallow access to nested mutable dictionaries (`state.d['nested']['a'] = 1`), bypassing immutability.
*   **Fix Verification:** Supervisor Architecture intercepts all accesses.
*   **Status:** ✅ **VERIFIED FIXED**.

---

## 2. 🤥 Marketing Claims vs. Reality

### 2.1. "True Parallelism" (Verified)
*   **Source:** `theus/engine.py` (lines 289-292), `theus/contracts.py`.
*   **Finding:** Theus v3.1 **Full Supports** Declarative Parallelism.
*   **Reality:** Adding `@process(parallel=True)` automatically dispatches execution to `InterpreterPool` (or `ProcessPool`). No manual API call needed.
*   **Status:** ✅ **VERIFIED**. Logic is in place and active.

### 2.2. "Zero-Copy" Scope (Verified Hybrid)
*   **Source:** `theus/context.py` (`HeavyZoneWrapper`, `SafeSharedMemory`), `src/shm_registry.rs`.
*   **Finding:** The "Hybrid Zero-Copy" model described in ADRs is **Implemented**.
*   **Reality:**
    *   **Light Data:** Pickled (Control Plane).
    *   **Heavy Data (`ctx.heavy`):** Uses `SharedMemory` + `numpy.ndarray(buffer=shm)`. This **IS Zero-Copy**.
    *   `HeavyZoneWrapper` automatically rehydrates memory views in Workers.
*   **Status:** ✅ **VERIFIED**. Zero-Copy works for Heavy Zone data as designed.

---

## 3. 🧩 Interoperability & DX Issues (Resolved)

### 3.1. Proxy Identity Crisis (Resolved)
- **Status:** ✅ Fixed (v3.1.2)
- **Problem:** `SupervisorProxy` failed `isinstance(proxy, dict)`.
- **Fix:** Registered `SupervisorProxy` as virtual subclass of `collections.abc.Mapping`.

### 3.2. Proxy Interoperability (Tương thích kém với thư viện ngoài)
*   **Trạng thái:** ✅ **Resolved** (Protocol Compliance)
*   **Mô tả:** `SupervisorProxy` không tương thích với `json.dumps` hoặc `Pydantic` default validation.
*   **Giải pháp:**
    *   Proxy đã implement giao thức `Mapping` của Python (`collections.abc.Mapping`).
    *   Hỗ trợ ép kiểu trực tiếp: `dict(ctx.domain)`.
    *   Hỗ trợ Pydantic serialization thông qua `model_config = ConfigDict(from_attributes=True)` (ORM Mode).
    *   Bổ sung phương thức helper `.to_dict()`.
*   **Workaround (Đã cũ):** Không cần hàm `unwrap_proxy`. Sử dụng `dict(proxy)` khi cần tương tác với FastAPI/JSON.abc.Mapping`.

### 3.3. Pickling Failure (Resolved)
- **Status:** ✅ Fixed (v3.1.2)
- **Problem:** Rust objects crashed `pickle.dumps()`.
- **Fix:** Implemented `__getstate__`, `__setstate__`, and `__getnewargs__` in `src/proxy.rs`.

### 3.3. Linter/Runtime Mismatch (`ctx.log`) (Resolved)
- **Status:** ✅ Fixed (v3.1.2)
- **Problem:** `ctx.log()` recommended by linter but missing at runtime.
- **Fix:** Added `log` method to `ContextGuard` in `src/guards.rs`.

### 3.4. Deadlock Risk (`execute_workflow`) (Mitigated)
- **Status:** ✅ Mitigated
- **Problem:** Blocking code in Async Loop.
- **Fix:** `engine.py` logic forces `asyncio.to_thread` or safe execution. Verified by Audit.

---

## 4. ⚔️ Concurrency & Resource Risks

### 4.1. Global CAS Starvation (Mitigated)
*   **Source:** `Conflict_Analysis.md`, `AUDIT_V3_0_2.md`
*   **Description:** Simple Global CAS causes Livelock for slow workers.
*   **Mitigation Verification:** `engine.py` Retry Loop + `conflict.rs` Backoff/VIP logic confirmed.
*   **Status:** ✅ **VERIFIED IMPLEMENTED**.

### 4.2. Zombie Memory Leaks (Resolved)
*   **Source:** `src/shm_registry.rs` (scan_zombies)
*   **Description:** Managed Allocator uses `/dev/shm`. Previously, crashes left orphaned files.
*   **Status:** ✅ **RESOLVED** (Startup-Scan + Registry Rewrite).
*   **Fix:** `MemoryRegistry` now performs a Startup Scan that checks PID liveness (via `sysinfo`). If a PID is dead, its SHM segments are unlinked and the Registry file is **Rewritten** to remove dead entries. Verified by `test_shm_pickling.py`.
