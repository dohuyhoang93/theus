# Theus V3.0.2 Architecture: The Process-Oriented Operating System

**Date:** Jan 2026
**Version:** 3.0.2 (Production Stable)
**Core Philosophy:** "Zero-Trust, Zero-Copy, Zero-Mutation."

Theus is not just a framework; it is a **Process-Oriented Operating System** running on top of Python/Rust. It strictly enforces separation of concerns through a unique 3-Axis Context Model and a Hybrid Microkernel architecture.

---

## 1. System Overview (Hybrid Microkernel)

Theus divides the world into two realms: the **Safe Userland** (Python) and the **Strict Kernel** (Rust).

```mermaid
graph TD
    subgraph "Pure Userland - Python"
        UserCode[User Process - @process]
        Linter[POP Linter - Static Analysis]
    end

    subgraph "Theus Kernel - Rust + Python Glue"
        Guard[ContextGuard - Runtime Firewall]
        Engine[Transaction Engine - CAS]
        Conflict[Conflict Manager - Backoff VIP]
        Heavy[Heavy Zone Allocator - Shared Mem]
    end

    subgraph "Infrastructure"
        RAM[System RAM]
        Disk[Persistence Store]
    end

    UserCode -->|Reads - Restricted| Guard
    UserCode -->|Writes - Delta| Engine
    Guard -->|Enforces| Linter
    Engine -->|Commits| RAM
    Engine -->|Manages| Conflict
    Heavy -->|Zero-Copy| RAM
```

*   **Rust Core:** Handles State, Concurrency, Locking, and Atomic Commits.
*   **Python Layer:** Provides the Developer Experience (Decorators, Linter, CLI).

---

## 2. The 3-Axis Context Model (State Physics)

Theus treats data as coordinates in a 3D space to enforce strict architectural rules.

```mermaid
mindmap
  root((Theus Context))
    Axis_X_Layer
      Global - Config
      Domain - Business Data
      Local  - Ephemeral
    Axis_Y_Semantic
      Input  - Read Only
      Output - Write Only
      Signal - Transient
      Error  - Failure
    Axis_Z_Zone
      DATA   - Consistent ACID
      HEAVY  - Zero Copy Blob
      META   - Observability
      SIGNAL - Event
```

### Detailed Breakdown
1.  **Axis X (Layer):** Who owns it?
    *   `ctx.domain`: The long-lived business state.
    *   `ctx.local`: Temporary scratchpad.
2.  **Axis Y (Semantic):** What can I do with it?
    *   **Enforced by:** Linter & Runtime Guard.
    *   *Rule:* You cannot write to an Input. You cannot read a Signal in a PURE process.
3.  **Axis Z (Zone):** How is it stored?
    *   **HEAVY Zone:** Uses `SharedMemory` to pass 2GB Tensors between processes in 0.1ms (Zero-Copy).
    *   **DATA Zone:** Uses `Arc<HashMap>` for thread-safe concurrent reads.

---

## 3. Process Execution Lifecycle

How a `@process` runs from start to finish, ensuring ACID properties.

```mermaid
sequenceDiagram
    participant Flux as Orchestrator
    participant Engine as Transaction Engine
    participant Guard as ContextGuard
    participant Func as User Process
    participant State as Rust Core

    Flux->>Engine: execute process_name
    Engine->>State: Get Snapshot Version N
    
    rect rgb(240, 248, 255)
        Note over Engine, Func: PHASE 1 - EXECUTION Pure Sandboxed
        Engine->>Guard: Creates Restricted View
        Engine->>Func: run ctx_proxy
        Func->>Guard: read input
        Guard-->>Func: return value Immutable
        Func->>Guard: write input
        Guard--xFunc: ❌ BLOCKED Read Only
        Func->>Engine: return Delta Changes
    end

    rect rgb(255, 240, 245)
        Note over Engine, State: PHASE 2 - COMMIT Atomic
        Engine->>State: CAS Version N, Delta
        alt Success
            State-->>Engine: OK New Version N+1
        else Conflict
            State-->>Engine: ❌ FAIL Version Mismatch
            Engine->>Engine: Backoff and Retry
        end
    end
```

---

## 4. POP Linter Integration (v3.1)

The Linter acts as the "Compiler" for architectural rules, running before the code even executes.

```mermaid
graph LR
    Code[Source Code .py] --> AST[AST Parser]
    AST --> Linter[POP Linter v3.1]
    
    Linter -->|Check| Rule1[POP-E01 - No Print]
    Linter -->|Check| Rule2[POP-E03 - No Network]
    Linter -->|Check| Rule3[POP-E05 - No Mutation]
    Linter -->|Check| Rule4[POP-C01 - Contract Integrity]
    
    Rule1 --> Report
    Rule2 --> Report
    Rule3 --> Report
    Rule4 --> Report
    
    Report -->|JSON/Table| Developer
    Report -->|Exit Code 1| CI_CD["CI Pipeline"]
```

### Key Rules
*   **POP-C01 (Contract Integrity):** Scans code body. If you touch `ctx.domain.user` but didn't declare `inputs=['domain.user']`, it screams.
*   **POP-E05 (Immutability):** Detects `ctx.x = 1`. Forces you to use `return {'x': 1}`.

---

## 5. Parallelism & Concurrency

Theus v3.0.2 introduces **True Parallelism** bypassing the GIL for Heavy workloads.

*   **ProcessPool:** Spawns separate Python Interpreters (Processes).
*   **Shared Memory:** Tensors in `HEAVY` zone are mapped into each child process's address space. **No pickling required.**
*   **Conflict Manager:**
    *   **VIP Locking:** If a critical process fails CAS 3 times, it gets a "VIP Ticket", pausing other writers until it succeeds.
    *   **Exponential Backoff:** Reduces contention storms.

---
*Created by Theus Architecture Team*
