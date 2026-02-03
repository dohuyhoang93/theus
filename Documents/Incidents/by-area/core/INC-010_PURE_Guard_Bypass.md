---
id: INC-010
title: PURE Guard "Ghost Write" Bypass
area: core
severity: medium
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-010: PURE Guard "Ghost Write" Bypass

## Summary
The `FilteredDomainProxy`, utilized by `RestrictedStateProxy` to enforce "Pure" function semantics, allows explicit attribute assignment (`ctx.domain.val = 1`) without raising an error. Due to the ephemeral nature of the proxy (re-created on property access), these writes are immediately discarded ("Ghost Writes") rather than persisting to the state. This creates a "Silent Loss" scenario where code appears to functionality mutate state but actually does nothing.

## Background
Theus enforces **POP (Process-Oriented Programming)** contracts via `SemanticType.PURE`. Pure processes are strictly read-only. To enforce this, the Engine wraps the State in a `RestrictedStateProxy` before passing it to the function. This proxy is intended to block all mutation attempts.

## What Went Wrong
*   **Confused Success:** A process marked `@process(semantic='pure')` can execute `ctx.domain.any_key = value` successfully.
*   **Silent Loss:** The value is written to the `__dict__` of the *transient* proxy instance.
*   **Read Failure:** Subsequent reads fail (because a new proxy is generated), or worse, if the user assigned to a local variable (`d = ctx.domain`), the local variable retains the mutated state, creating an undocumented, un-auditable local cache.

## Root Cause Analysis
### 1. Integrative Critical Analysis (The Micro Cause)
*   **The Trap (False Assumption):** The developer assumed that implementing `__setitem__` (or relying on underlying immutable types) was sufficient to prevent mutation.
*   **The Truth:** Python classes are open by default. Without an explicit `__setattr__` override, assigning `obj.attr = val` writes to the instance's `__dict__`.
*   **Essence:** The Proxy was designed as a "Window" (Start-Through) but functioned as a "Ghost" (Ephemeral Container). The user was writing on the window glass, not the object behind it.

### 2. Systems Thinking Engine (The Macro Cause)
*   **Dynamics:** The `RestrictedStateProxy` uses a **Factory Pattern** for its properties (`@property def domain: return FilteredDomainProxy(...)`).
    *   *Effect:* Every access creates a fresh object.
    *   *Loop:* `Write(Proxy A) -> Success -> Drop(Proxy A) -> Read(Proxy B) -> Miss`.
*   **Structure:** The lack of a `__setattr__` guard on the *Proxy Class* itself is the structural gap. The system focused on protecting the *Core State* (which stayed safe) but neglected the *User Experience* of the Proxy.

## Impact
*   **Data Integrity:** Safe (Core state is untouched).
*   **Code Correctness:** Critical. Developers will write code that silently does nothing, leading to hard-to-debug logic errors.
*   **Security:** Low (Attacker cannot corrupt system, only confuse local logic).

## Resolution
1.  **Proxy Seal:** Implemented strict `__setattr__`, `__setitem__`, `__delattr__`, `__delitem__` on `FilteredDomainProxy` to raise `ContractViolationError`.
2.  **Deep Guard:** Updated `FilteredDomainProxy` to return **Immutable Views** of referenced objects:
    *   `list` -> `tuple`
    *   `dict` -> `types.MappingProxyType`
    *   Prevents "leak by reference" where a user could modify a mutable object returned by the read-only proxy.

## Verification
*   **Comprehensive Suite:** `tests/02_safety/test_pure_guard_full_matrix.py` (All 5 Categories PASS).
*   **Edge Case Proof:** `ctx.domain.list.append(1)` now raises `AttributeError: 'tuple' object has no attribute 'append'`.

## Lessons Learned
*   **Python Proxies:** Always override `__setattr__` when creating a read-only view.
*   **UX Safety:** "Silent Failure" is often worse than "System Crash".
