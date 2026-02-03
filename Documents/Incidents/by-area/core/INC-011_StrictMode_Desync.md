---
id: INC-011
title: Strict API Ambiguity & Desynchronization
area: core
severity: high
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-011: Strict API Ambiguity & Desynchronization

## Summary
The legacy `strict_mode` API in Python was ambiguous and mistakenly coupled two distinct concepts: **Input Policy (Guards)** and **Concurrency Policy (CAS)**. Furthermore, this flag was not correctly propagated to the Rust Core, leading to a state where Rust protections were silently inactive.

## Technical Detail
*   **Original State:** 
    *   Python had `strict_mode` (Guards) and `strict_cas`.
    *   Rust had only `strict_mode` (which enforced BOTH).
    *   **Desync:** Python `strict_mode` was never passed to Rust.
*   **Conflict:** Even if passed, enabling Rust's `strict_mode` would force Strict CAS behavior, breaking users who wanted "Guards + Smart CAS".

## Resolution (POP v3.1 Refactor)
Instead of a simple patch, we fully refactored the API to align with the POP-Theus Manifesto (Explicit Configuration).

*   **API Change:** `strict_mode` has been **REMOVED** and replaced by `strict_guards`.
*   **Rust Core:** Split the monolithic `strict_mode` into two independent flags:
    1.  `strict_guards`: Controls I/O, Zones, and Privacy.
    2.  `strict_cas`: Controls Version matching strictness.
*   **Python Engine:** Updated `__init__` to accept `strict_guards` and `strict_cas` and pass them explicitly to Rust setters.

## Verification
The script `verify_strict_decoupling.py` confirms that these two features can now be toggled independently:
*   Case 1: `strict_guards=True`, `strict_cas=False` -> Secure Inputs, Smart Merging.
*   Case 2: `strict_guards=True`, `strict_cas=True` -> Secure Inputs, Strict Versioning.

## Related
*   **Files:** `theus/engine.py`, `src/engine.rs`, `src/guards.rs`
*   **Test:** `tests/02_safety/verify_strict_decoupling.py`
