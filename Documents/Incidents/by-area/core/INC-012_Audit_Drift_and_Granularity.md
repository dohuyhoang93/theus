---
id: INC-012
title: Audit System Drift & Granularity Mismatch
area: core
severity: high
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-012: Audit System Drift & Granularity Mismatch

## Summary
Two critical issues were identified revealing a systemic failure in the verification strategy:
1. **Disconnected Brain:** Python Validator was not hooked into Engine. Audit rules in YAML were never enforced.
2. **Granularity Mismatch:** Implementation enforced Global Policy only, ignoring per-rule `level` and `max_threshold` from spec.

## Background
Theus uses a `spec.yaml` (Audit Recipe) to define validation rules per-process. These rules specify `level` (S/A/B/C) and `max_threshold` for fine-grained control. The Engine should load this spec and enforce it at Input/Output Gates.

## What Went Wrong
1.  **Validator Not Wired:** `TheusEngine` had `audit_system` but no `AuditValidator` calling it on violations.
2.  **Global-Only Logic:** Rust `log_fail(key)` ignored per-rule overrides, always using Global `AuditRecipe` values.

## Impact
*   **Affected:** All audit logic. The system ran WITHOUT any active policy enforcement.
*   **Behavior:** Critical rules (Level S) were treated the same as warnings (Level C).
*   **Severity:** High. Security/Policy gaps. "Flying Blind".

## Root Cause
*   **Unit Test Tunnel Vision:** Legacy `tests/07_audit` tested `AuditSystem` in isolation. No test verified Engine called it.
*   **Silent Simplification:** Rust Core was simplified for performance, dropping per-rule parameters without updating Design Spec.

## Resolution
### Phase 1: Re-Integrate (Validator)
*   Created `theus/validator.py` with `validate_inputs()` and `validate_outputs()`.
*   Wired into `TheusEngine._attempt_execute()` (Input Gate) and `execute()` (Output Gate).

### Phase 2: Granularity Upgrade (Rust API)
*   Updated `log_fail()` signature in `src/audit.rs`:
    ```rust
    fn log_fail(&mut self, key, level: Option<AuditLevel>, threshold_max: Option<u32>)
    ```
*   Validator maps spec strings ("S"/"A"/"B"/"C") to Rust `AuditLevel` and passes overrides.

## Preventive Actions
*   **Integration Test:** `tests/03_audit/verify_real_spec_flow.py` tests mixed levels (B blocks, C counts, S stops).
*   **Documentation:** Updated `/en/Chapter_08.md` and created `/ai/09_AUDIT_SYSTEM_INTERNALS.md`.

## Related
*   **ADR:** Documents/Architecture/02_ADR/008_Context_Zone.md

## Lessons Learned
*   **Unit Tests are Deceptive:** Testing a component in isolation does not prove it is USED by the system.
*   **Spec vs Code:** When refactoring for performance, features can be silently dropped.
