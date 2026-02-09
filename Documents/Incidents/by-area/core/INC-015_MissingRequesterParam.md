---
id: INC-015
title: Missing Requester Parameter in CAS API prevents VIP Access
area: core
severity: Medium
status: resolved
created: 2026-02-05
author: Antigravity
---

# Incident Report: INC-015 Missing Requester Param

## 1. Summary
The `TheusEngine.compare_and_swap` Python Method signature failed to include the `requester` parameter, preventing callers from identifying themselves to the Rust Core. This rendered the **Priority Ticket (VIP)** feature inaccessible from Python.

## 2. Background
Chapter 20 documents a "Priority Ticket" system where a struggling worker gets `wait_ms=1` access while others get `System Busy`. This relies on `conflict_manager.is_blocked(requester)`.

## 3. What Went Wrong
*   **Rust Layer (`src/engine.rs`):** The `compare_and_swap` function in Rust correctly accepts `requester: Option<String>`.
*   **Python Layer (`theus/engine.py`):** The Python wrapper function signature was:
    ```python
    def compare_and_swap(self, expected_version, data=None, heavy=None, signal=None):
    ```
*   **The Gap:** The `requester` argument was completely missing. Calls from Python were treated as `requester=None` (Anonymous), meaning even a VIP-holding worker was treated as Anonymous and blocked by its own ticket.

## 4. Immediate Resolution
Added `requester=None` to the Python signature and forwarded it to `self._core.compare_and_swap`.

## 5. Micro Analysis (Logic & Mental Model)
> *Method: Integrative Critical Analysis (@micro)*

*   **The Trap:** "Parameter Blindness". The developer updating the Python bindings likely focused on the Data payload (`data`, `heavy`, `signal`) and overlooked the Metadata payload (`requester`) because it wasn't required for the "Happy Path".
*   **The Truth:** Optional parameters in Rust bindings must be explicitly mirrored in Python if they are to be used. Python doesn't automatically pass "extra" args unless `**kwargs` is used (which obscures the API).

## 6. Macro Analysis (Systemic & Architecture)
> *Method: Systems Thinking Engine (@macro)*

*   **Structural Root Cause:** **Manual/Dual Maintenance of Signatures**. 
    *   We define the Function in Rust (`#[pyclass]`).
    *   We redefine the Wrapper in Python (`class TheusEngine`).
    *   **Drift is Inevitable** without automated binding generation (or `.pyi` generation from Rust).
*   **Missing Feedback Loop:** The "VIP Ticket" feature was tested in Rust Unit Tests (which call Rust functions directly) but **never tested from Python** until `tests/manual/verify_smart_cas.py` was created today.

## 7. Ethical Audit
> *Method: Intellectual Virtue Auditor (@ethics)*

*   **Intellectual Humility:** We claimed in Chapter 20 that the feature was "Active by default". Technically true (Rust Core active), but practically false (Unreachable). We must admit this documentation was "Theoretical" rather than "Verified".
*   **Intellectual Integrity:** Resolving this requires us to not just fix the bug, but verify *why* we thought it worked. We relied on the *Architecture* being sound, ignoring the *Interface*.

## 8. Resolution Plan


### 8.1. Action Plan
1.  **Immediate (Done):** Patch `theus/engine.py` to expose `requester`.
2.  **Verification (Done):** `verify_smart_cas.py` confirms successful VIP access.
3.  **Systemic (Done):** Implemented `scripts/gen_stubs.py` (using `stubgen`) to automatically sync Python Type Stubs with Rust signatures. 
4.  **Defense Layer (Done):** Integrated into CI/CD (`.github/workflows/CI.yml`) to enforce `git diff --exit-code` on stubs, ensuring no signature drift occurs in the future.
5.  **True Defense (Done):** Created `tests/verify_api_parity.py` to strictly enforce runtime signature matching between Python Wrappers and Rust Core. This caught 2 additional deviations (`set_schema`, `transaction`).
6.  **Process (Done):** Codified the new workflow in `Documents/THEUS_DEVELOPMENT_WORKFLOW.md`.

### 8.3. Conclusion
**RESOLVED**. VIP System is now accessible and future-proofed against regression.


