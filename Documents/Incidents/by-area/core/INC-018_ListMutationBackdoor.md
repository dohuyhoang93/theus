---
id: INC-018
title: Global State Mutation Backdoor via List Interop
area: core
severity: critical
introduced_in: v3.0.0
fixed_in: open
status: open
---

# INC-018: Global State Mutation Backdoor via List Interop

## Summary
A critical architectural flaw was identified where the `TheusEngine` global state can be mutated without a transaction or permission check by performing in-place modifications on `list` objects returned by `domain_proxy()`. This bypasses the framework's "Zero Trust" and "Immutable State" guarantees.

## Background
Theus uses a "Passive Inference" model for high-performance Python collection interop. Inside a `Transaction`, `list` objects are returned as **Shadow Copies** (shallow copies tracked by the engine). The engine then diffs these copies at commit time to infer changes. For `dict` and other objects, it uses a `SupervisorProxy` to intercept attribute access (`__setattr__`).

## What Went Wrong
While `dict` access is protected by `SupervisorProxy` (which blocks writes outside transactions), `list` types were intentionally left "un-proxied" for performance reasons. 

The logic in `SupervisorProxy::__getattr__` (Rust) checks if a value is a `dict` or has a `__dict__`. If neither (as is the case for `list`), it returns the **raw reference** (line 152 of `proxy.rs`). 

When accessed via `engine.state.domain_proxy()`, there is no `Transaction` context to create a Shadow Copy. Therefore, the user receives a direct C-level reference to the global state's internal memory. Calling `.append()`, `.extend()`, or `__setitem__` on this list mutates the system's "Source of Truth" immediately and silently.

## Impact
- **Affected:** All user state using lists accessed via the Supervisor API (`domain_proxy`).
- **Corruption:** Unauthorized, un-audited, and irreversible modification of the committed state.
- **Security:** Complete breakdown of the isolation layer. A "Read-Only" view can be used as a write-backdoor.

## Root Cause
### Systemic Analysis (Systems Thinking)
- **Structure:** Inconsistency between `ContextGuard` (which *always* shadows lists) and `SupervisorProxy` (which *never* shadows/proxies lists).
- **Incentive:** The "Passive Inference" design prioritized zero-overhead reads for lists, assuming that without a `Transaction`, no harm could occur because there was no "Commit" path. It failed to account for the fact that a `list` is a mutable container in Python memory.
- **Boundary Failure:** The framework assumes the "Commit" logic is the only way to update state, ignoring "Internal Mutability" of leaked references.

### Critical Dissection (Intellectual Virtues)
- **Invalid Assumption:** "Intercepting `__setattr__` is sufficient for security." This is true for objects but false for built-in mutable collections.
- **Mental Model:** The developers viewed `list` as a "Value" rather than a "Shared Resource Counter-part".

## Why This Was Hard to Detect
- **Performance Trade-off:** Proxing every list access would have triggered massive overhead, so the leak was hidden behind an "Optimization" banner.
- **Partial Protection:** Because `dict` mutation *was* blocked, the failure in the manual suite for lists was overlooked or assumed to be "intended behavior" for interop.

## Strategic Analysis (Integrative-Critical Analysis)

> **CORE INSIGHT:** The system suffers from a "Reference Leakage" where optimized list access defaults to shared-memory pointers instead of immutable snapshots, violating the framework's isolation invariants.

### 1. Critical Dissection
* **The Trap:** The assumption that "If there is no Transaction, there is no risk of commit" (Q5).
* **The Truth:** In-place mutation of a shared list on the Heap is its own commit (Q9).

### 2. Systemic Context
* **Breaking Point:** Multi-agent environments where one agent uses `domain_proxy` to "peek" and ends up polluting the state of all others (Q13).
* **Ripple Effect:** Total loss of deterministic replayability if state changes happen outside the delta-log (Q15).

### 3. Proposed Leverage Point
### 3. Confirmed Resolution (Strategic Pivot)
*   **The Solution:** Adopt **[RFC-001: Semantic Policy Architecture](../../Architecture/03_RFC/RFC-001_Semantic_Policy_Architecture.md)**.
    *   **From:** "Patching the backdoors" (Tactical).
    *   **To:** "Capability-Based Security" (Strategic).
    *   **Mechanism:**
        1.  **Zone Physics:** Define `log_` prefix as intrinsically `AppendOnly`.
        2.  **Capability Lenses:** Rust Core calculates a dynamic bitmask `[READ, APPEND]` for the list.
        3.  **Supervisor Enforcement:** Accessing `log_events` outside a transaction returns a **ProtectedProxy** that physically blocks `.pop()` or `.clear()` while allowing `.append()` (if permitted by policy).
        4.  **Zero-Leak:** Raw C-pointers are never returned if the computed Lens does not grant full `UNSAFE` capability.

## Lessons Learned
- **Built-ins are Backdoors:** Never return a raw mutable Python built-in from a secured boundary.
- **Contract Symmetry:** If `ContextGuard` handles a type specially (Shadowing), `SupervisorProxy` must handle it with equivalent security posture.

## Related
- **INC-001:** Silent Loss of Mutations (Related to List Diffs)
- **INC-001:** Silent Loss of Mutations (Related to List Diffs)
- **RFC-001:** Semantic Policy Architecture (The Fix)
