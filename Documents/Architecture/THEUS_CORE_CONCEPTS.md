# Theus Core Concepts: The Physics of Architecture

This document documents the fundamental architectural concepts of Theus, discovered through deep code analysis of the v3.0+ codebase. It explains the "Physics" that governs how data and logic interact within the framework.

## 1. The 3-Axis Context Model (🧊 X-Y-Z)

Theus defines state not as a flat list of variables, but as a 3-dimensional space. Every piece of data has 3 coordinates: **Layer**, **Semantic**, and **Zone**.

### 🟢 Axis X: Layer (Scope & Lifecycle)
*Answers: "Who owns this data and how long does it live?"*

| Layer | Python Access | Description | Implemented In |
| :--- | :--- | :--- | :--- |
| **Global** | `ctx.global` | **Immutable Configuration.** Loaded at startup. Visible to all processes. | `BaseGlobalContext` |
| **Domain** | `ctx.domain` | **System State.** The core business data (User, Order, Inventory). Persists across the session. | `BaseDomainContext` |
| **Local** | `ctx.local` | **Ephemeral.** Temporary variables within a single Process. Destroyed upon return. | Dict (Auto-created) |

### 🟡 Axis Y: Semantic (Intent & Usage)
*Answers: "What is the allowed direction of data flow?"*

Defined in `@process` contracts and strictly enforced by the **Linter** and **Runtime Guard**.

| Semantic | Contract Field | Implementation Rule |
| :--- | :--- | :--- |
| **Input** | `inputs=['...']` | **Read-Only.** Runtime enforces immutability via `ContextGuard`. |
| **Output** | `outputs=['...']` | **Write-Only.** Changes are buffered as `Delta` and committed atomically. |
| **Side Effect** | `side_effects=['...']` | **External Impact.** API Calls, DB Writes. Must be declared or Linter (POP-E03) will block. |
| **Error** | `errors=['...']` | **Expected Failures.** Defines the "Unhappy Path" explicitly. |

### 🔴 Axis Z: Zone (Physics & Storage)
*Answers: "How is this data stored and passed?"*

Routed automatically based on variable name prefixes.

| Zone | Prefix (Convention) | Storage Mechanism | Use Case |
| :--- | :--- | :--- | :--- |
| **DATA** | (None) | **Transactional Memory.** Supports ACID, Rollback, Snapshots. | Core Business Logic (`balance`, `status`). |
| **SIGNAL** | `sig_`, `cmd_` | **Transient Message.** Auto-clears after 1 tick. No persistence. | Event-Driven Trigger (`sig_user_login`). |
| **META** | `meta_` | **Observability.** Logging, Tracing, Metrics. Read-only for logic. | Debugging, Audit Logs. |
| **HEAVY** | `heavy_` | **Shared Memory (Zero-Copy).** Bypasses Transaction Log. | Large Tensors (>1MB), Images. |

---

## 2. Process Semantic Types (`PURE` vs `EFFECT` vs `GUIDE`)

Theus classifies logic into 3 distinct types to help the Engine (and AI) optimize execution.

### ✨ 1. PURE (The Strict Helper)
*   **Definition:** Deterministic function. Same Input -> Same Output. No Side Effects.
*   **Engine Enforcement:** **YES**.
    *   **Restricted View:** The runtime wraps `ctx` in a `RestrictedStateProxy`, completely blocking access to `send_signal`, `log`, or any external I/O.
    *   **Input Blocking:** Cannot read variable inputs (`SIGNAL`, `META`).
*   **Use Case:** Calculations, Parsing, Tensor Math.

### 🔌 2. EFFECT (The Standard Worker)
*   **Definition:** Standard logic that interacts with the world.
*   **Engine Enforcement:** **NO** (Standard Mode).
    *   Has full access to Context (subject to Contract rules).
    *   Linter still checks for banned modules (e.g., `requests` without permission).
*   **Use Case:** Database CRUD, API Client, Workflow Logic.

### 🧭 3. GUIDE (The AI Navigator)
*   **Definition:** Logic used for reasoning, decision making, or prompt refinement. Does not alter Business Data.
*   **Engine Enforcement:** **NO** (Currently acts like `EFFECT`).
*   **Future Roadmap:**
    *   **Priority Scheduling:** Will run before `EFFECT` processes to "warm up" the prompt context.
    *   **Cost Tracking:** Engine will track Token Usage specific to GUIDE processes.
*   **Use Case:** `refine_prompt`, `router_decision`, `chain_of_thought`.

---

## 3. Implementation Map

Where to find these concepts in the code:

*   **Contracts:** `theus/contracts.py` -> Defines `@process`, `SemanticType`.
*   **Layers:** `theus/context.py` -> Defines `BaseSystemContext` schema.
*   **Zones:** `theus/zones.py` -> Logic for `resolve_zone(key)`.
*   **Pure Enforcement:** `theus/engine.py` -> `_create_restricted_view` & `RestrictedStateProxy`.
*   **Linter Rules:** `theus/linter.py` -> `POP-E**` and `POP-C**` rules.
