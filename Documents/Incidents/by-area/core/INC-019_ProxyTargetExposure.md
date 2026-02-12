---
id: INC-019
title: Critical Security Bypass via SupervisorProxy._target Exposure
area: core
severity: critical
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-019: Critical Security Bypass via SupervisorProxy._target Exposure

## 1. Summary
A "0-Day" vulnerability was identified in the `SupervisorProxy` implementation where the `_target` attribute is exposed to Python via `#[pyo3(get)]`. This allows any Python code to retrieve the underlying raw object (e.g., `dict`, `list`) and mutate it directly, completely bypassing Theus's 3-Axis security model, Transaction logging, and Audit controls.

## 2. Background
Theus relies on `SupervisorProxy` (Rust) to intercept all mutations (`__setitem__`, `__setattr__`) to objects within a restricted context. The design assumes that the Proxy is a sealed envelope that only allows approved operations based on the 3-Axis Intersection (Domain, Semantic, Zone). The `_target` field holds the reference to the actual data.

## 3. What Went Wrong
The Rust struct definition for `SupervisorProxy` inadvertently included the `#[pyo3(get)]` macro on the `target` field:

```rust
#[pyclass(module = "theus_core", subclass)]
pub struct SupervisorProxy {
    /// The wrapped Python object
    #[pyo3(get, name = "_target")] // <--- THE VULNERABILITY
    pub target: Py<PyAny>,
    // ...
}
```

This macro automatically generates a public getter, compliant with Python's descriptor protocol. While named `_target` (implying private), it is fully accessible to any code, enabling the "Unmasking" attack vector demonstrated in `repro_hardcore_attack.py`.

## 4. Impact
*   **Security:** Total compromise. Any malicious or buggy code can unwrap the proxy and corrupt the state.
*   **Integrity:** Mutations via `_target` are not logged in the Transaction Delta, breaking the Deterministic Replay and Audit Log guarantees.
*   **Scope:** Affects all Data Zones and Heavy Zones.

## 5. Root Cause Analysis (Deep Dive)

### 5.1 Micro Analysis (Technical/Logic)
*   **The Error:** Using `#[pyo3(get)]` for a field that should be internal-only (Rust-private).
*   **Mental Model Mismatch:** The developer likely added `#[pyo3(get)]` for debugging convenience or introspection (to see what's inside), forgetting that in a capability-based system, *visibility is capability*.
*   **Assumption:** "If I name it with an underscore, people won't touch it." (Security by Convention vs. Security by Enforcement).

### 5.2 Macro Analysis (Systemic/Process)
*   **Test Coverage:** Security tests focused on *functional* blocking (trying to write to the proxy) but missed *structural* leakage (inspecting the proxy itself).
*   **Review Process:** The FFI boundary (Rust <-> Python) is a blind spot. Python linters don't see Rust structs, and Rust compilers don't know Python security semantics.
*   **Design Trade-off:** The "Zero-Code" / "Zero-Copy" philosophy encouraged exposing internals for performance, which inadvertently exposed them for exploitation.

### 5.3 Ethical & Virtue Audit
*   **Humility:** We claimed "Dormant Power" was proven, but a simple attribute access disproved it. We must admit that our "Proof" was too narrow.
*   **Integrity:** We must fix this immediately, even if it breaks some internal debugging tools that might rely on `_target`.

## 6. Resolution Plan

1.  **Immediate Fix:**
    *   **[COMPLETED]** Renamed `target` field to `inner` in `src/proxy.rs`. This breaks any implicit binding to `_target` by PyO3.
    *   **[COMPLETED]** Removed `#[pyo3(get)]` macro from the field.
    *   **[COMPLETED]** Changed visibility to `pub(crate)` to ensure internal-only access.
    *   **[VERIFIED]** `repro_hardcore_attack.py` confirms `_target` is no longer accessible (`AttributeError`).

2.  **Structural Improvement:**
    *   Audit all `#[pyo3(get)]` usage completed. No other critical leaks found in `proxy.rs`.

3.  **Process Update:**
    *   Added `repro_hardcore_attack.py` to the regression suite.

## 7. Operational Status
*   **Status:** Resolved
*   **Owner:** Antigravity
*   **Fixed In:** v3.0.22 (Current Dev Build)
