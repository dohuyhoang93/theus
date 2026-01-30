---
id: INC-005
title: Legacy Context Reference Leak
area: core
severity: critical
introduced_in: v3.0.0
fixed_in: v3.0.2
status: resolved
---

# INC-005: Legacy Context Reference Leak

## Summary
The accessor `ctx.domain_ctx` returned raw references to the underlying state dictionary. This allowed users to mutate state bypassing the Transaction/Supervisor mechanism entirely, violating the core security premise of Theus.

## Root Cause
- **Leak:** The property getter returned `self._data` directly instead of wrapping it in a `SupervisorProxy`.
- **Assumption:** Assumed developers would respect convention (`_underscore` vars).

## Resolution
- **Mandatory Proxy:** All accessors in `structures.rs` now wrap return values in `SupervisorProxy`.
- **Audit:** `guards.rs` enforces this wrapping.
