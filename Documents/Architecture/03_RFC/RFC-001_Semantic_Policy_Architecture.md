---
id: RFC-001
title: Semantic Policy Architecture (The 3-Axis Enforcement)
type: Standards Track
status: Proposed
author: Antigravity (AI Architect)
created: 2026-02-06
target_version: Theus v3.2
---

# RFC-001: Semantic Policy Architecture

## 1. Executive Summary

This RFC introduces a **Semantic Policy Architecture** to resolve the logical disconnect between Python's flexible context model and Rust's rigorous state enforcement. It addresses the critical vulnerability **INC-018** (List Mutation Backdoor) by replacing binary "Active/Passive" security with a fine-grained **Capability-Based Lens** system.

This architecture unifies the **3-Axis Context Model** (Layer, Semantic, Zone) into a single enforcement engine, ensuring that data "Physics" defined in Python are respected by the Rust Core at the FFI boundary.

---

## 2. Problem Statement: The Semantic Gap

Theus v3.0 relied on a binary assumption:
*   **Inside Transaction:** Safe (Shadow Copy active).
*   **Outside Transaction:** Passive (Return raw reference for performance).

**The Failure (INC-018):** `List` objects are mutable by nature. Returning a raw reference to a list outside a transaction allowed code to mutate global state without audit logging or rollback protection, effectively bypassing the framework's integrity guarantees.

**Root Cause:** The Rust Core lacked **Semantic Awareness**. It saw data as "Just a List" rather than "An Append-Only Event Log" or "An Immutable Configuration".

---

## 3. The Core Concept: Capability-Based Lenses

Instead of passing raw data, the Rust Core now wraps every access in a **Lens** (Proxy/Guard). This Lens is not a static view but a dynamic **Capability Bitmask**.

| Capability | Allowed Operations |
| :--- | :--- |
| **READ** | `__getattr__`, `__getitem__` |
| **APPEND** | `.append()`, `+=`, `.extend()` |
| **UPDATE** | `__setitem__`, `__setattr__` |
| **DELETE** | `.pop()`, `del`, `.clear()` |

The Lens strictly enforces these capabilities at the runtime level. If code calls `.pop()` through a Lens missing the `DELETE` bit, a `PermissionError` is raised immediately.

---

## 4. Architectural Convergence: The 3-Axis Integration

The "Lens" configuration is determined by calculating the intersection of Theus's 3 Core Axes.

### 4.1. The Hierarchy of Law (Precedence)

1.  **Level 1: The Physics (Axis Z & X - Born in `context.py`)**
    *   **Role:** Sets the **Hard Ceiling** (Maximum Theoretical Capability).
    *   **Source:** Defined by Zone Prefixes (`log_`, `meta_`) or explicit `Annotated` types.
    *   **Rule:** No process can override the Physics Ceiling (except Admin).

2.  **Level 2: The License (Axis Y - Granted in `@process`)**
    *   **Role:** An **Activation Permit**.
    *   **Source:** The `outputs=['...']` decorator.
    *   **Rule:** It elevates the Lens capabilities **up to** the Physics Ceiling.

### 4.2. The Universal Physics Table (Zone Laws)

| Zone | Prefixes | Physics Ceiling | Philosophy (The "Why") |
| :--- | :--- | :--- | :--- |
| **DATA** | *(None)* | `READ, APPEND, UPDATE, DELETE` | **Mutable State.** Business logic requires full freedom to mold the state. |
| **SIGNAL** | `sig_`, `cmd_` | `READ, APPEND` | **The River.** Events flow forward. You cannot "undo" (Delete) or "change" (Update) an emitted event. |
| **LOG** | `log_`, `audit_` | `READ, APPEND` | **The History.** The past is immutable. You can only append new entries. |
| **META** | `meta_` | `READ, UPDATE` | **The Config.** You can tune settings (Update) but structural deletion is forbidden. |
| **HEAVY** | `heavy_` | `READ, UPDATE (Ref)` | **The Boulder.** Shared Memory pointers. You can swap the pointer, but deep mutation is un-audited. |

---

## 5. The Logic of Elevation (Capability Algebra)

The final capability of a Lens is calculated as:
`FinalLens = (ProcessRequest) INTERSECT (ZoneCeiling)`

### The Elevation Matrix

| Intrinsic Zone (Ceiling) | Default View (No Process) | Process: `outputs=[]` (Standard Elevation) | Process: `outputs=["path:pop"]` (Explicit) | Admin Transaction (Override) |
| :--- | :--- | :--- | :--- | :--- |
| **STANDARD** (No prefix) | `READ` | `READ, UPDATE, APPEND, DELETE` | `READ, DELETE` | `ALL` |
| **APPEND_ONLY** (`log_`) | `READ` | `READ, APPEND` | **BLOCKED** (Hit Ceiling) | `ALL` |
| **IMMUTABLE** (`meta_`) | `READ` | `READ, UPDATE` (Reload) | **BLOCKED** | `ALL` |
| **CONSTANT** (`const_`) | `READ` | **BLOCKED** | **BLOCKED** | **BLOCKED** |

---

## 6. Under the Hood: Dynamic Policy Overlays

How does Rust know which Policy to apply?

**The "View-Policy" Model:**
Policy is **not stored on the Data Object**. It is stored on the **ContextGuard** (The Lens).

1.  **Instantiation:** When a Process starts, python creates a `ContextGuard` specific to that Process ID.
2.  **Injection:** The `outputs` list is injected into this Guard.
3.  **Overlay:** When accessing `ctx.domain.logs`, the Guard calculates the intersection of the `logs` Zone Physics and the injected `outputs` License.
4.  **Enforcement:** It returns a `SupervisorProxy` configured with the specific `u8` capability bitmask for that interaction.

This allows **Process A** to see `logs` as `AppendOnly` while **Process B** (an Admin process) sees it as `Mutable`, all while accessing the same underlying memory in Rust.

---

## 7. Paradox Resolution

**Implicit vs. Explicit Definition:**
*   **Implicit:** `sig_email` (Prefix) -> Physics = `APPEND_ONLY`.
*   **Explicit:** `sig_email: Annotated[List, Mutable]` -> Physics = `MUTABLE`.

**Rule:** **Explicit Annotation Overrides Implicit Prefix.**
*   *Note:* The Linter (`theus check`) will flag this as a "Style Violation" (Confusing Naming), but the Runtime will honor the Explicit definition.

---

---

## 8. Performance & Optimization

To handle the "Loop of Death" scenario (1 million rapid process spawns), the Rust Core must not allocate a new `ContextGuard` for every single call.

**The Flyweight Guard Pattern:**
*   **Problem:** Creating 1M `ContextGuard` structs + 1M `HashMap` clones = Massive Heap Pressure.
*   **Solution:** Capabilities are finite. The number of unique "Output combinations" in an app is often < 100.
*   **Implementation:** 
    1.  The `ContextGuard` identifies a "Signature" (e.g., hash of string `outputs=['log_events']`).
    2.  It checks a `ThreadLocal<HashMap<Signature, Arc<Guard>>>`.
    3.  If found, it reuses the existing, immutable `Arc<Guard>`.
    4.  **Result:** Zero allocation for valid recurring processes.

---

## 9. Tooling Requirements

The Policy Architecture relies heavily on the **Theus Linter** to prevent "Semantic Drift".

**New Linter Rules:**
1.  **POP-E04 (Paradox Check):** Flag any field that combines a "Static Prefix" (`log_`, `sig_`, `meta_`) with a `Mutable` type annotation.
    *   *Message:* "Detected Paradox: 'log_history' is marked Mutable. Rename to 'data_history' or remove Mutable annotation."
2.  **POP-E05 (Refactor Risk):** If a variable is renamed from `log_X` to `data_X`, the Linter must scan all `@process` usages to warn about implicit policy relaxation.

---

---

## 10. Attack Surface Analysis (Python Mutation Vectors)

Theus addresses the specific mutation mechanism of Python as follows:

| Vector | Mechanism | Defense Layer |
| :--- | :--- | :--- |
| **Direct Assignment** | `obj.attr = x` | Intercepted by `SupervisorProxy.__setattr__` (Rust). |
| **Item Assignment** | `obj[key] = x` | Intercepted by `SupervisorProxy.__setitem__` (Rust). |
| **In-Place Method** | `list.append(x)` | Intercepted by `SupervisorProxy.__getattr__`. Returns a "Guarded Method" that checks capability before execution. |
| **Augmented Assign** | `x += 1` | **Blocked by Default.** The `SupervisorProxy` does not implement `__iadd__`, causing a `TypeError`. This is "Safe Failure". |
| **Dict Introspection** | `obj.__dict__` | **Proxied.** Access returns a `SupervisorProxy` wrapping the `__dict__`. Writes to this dict are intercepted via `__setitem__`. |
| **Class Patching** | `obj.__class__` | **Blocked.** Access to attributes starting with `_` is denied by default to prevent runtime monkey-patching. |
| **C-Level Pointer** | `ctypes` / `gc` | **Out of Scope.** We defend against "Code Logic Errors", not "Malicious Root Attacks". |

---

## 11. Migration Strategy

To adopt RFC-001:
1.  **Refactor Context:** Organize `context.py` using `Namespace` and apply prefixes (`meta_`, `log_`) to existing fields.
2.  **Audit Processes:** Run the linter to ensure all mutated fields are declared in `outputs`. The new strict mode will block undeclared mutations.
3.  **Update Admin Scripts:** Any script performing "illegal" cleanup (like deleting logs) must be wrapped in `AdminTransaction`.
