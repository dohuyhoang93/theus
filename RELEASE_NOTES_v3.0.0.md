# Theus v3.0.0 "The Iron Mold" Release Notes

**Date:** 2026-01-16
**Status:** Stable / Golden Build

> **"The Iron Mold"** marks the most significant architectural shift in Theus history. We have replaced the Python core with a high-performance **Rust Microkernel**, bringing strict Thread Safety, Transactional Memory, and Zero-Copy serialization to the agentic world.

---

## 🚀 Major Features

### 1. The Rust Microkernel
The heart of Theus is now written in Rust.
*   **Zero-Copy Context:** Uses `Arc<T>` internals to share massive data (like ML models) between Python and Rust without copying RAM.
*   **Transactional Memory:** All state updates are atomic. `ctx.update()` either fully succeeds or fully rolls back.
*   **Thread Safety:** The Global Interpreter Lock (GIL) is released during heavy operations, allowing true parallelism.

### 2. True Parallelism (Sub-Interpreters)
Leveraging Python 3.14+ `concurrent.interpreters` (PEP 734):
*   **Isolate Execution:** Run agent processes in separate sub-interpreters with their own GIL.
*   **Shared Heap:** Data stored in `ctx.heavy` remains accessible across interpreters via the Rust backbone.

### 3. SignalHub (Tokio Powered)
A newly designed event system backed by `tokio::sync::broadcast`.
*   **Throughput:** Capable of handling >**2.7 Million events per second**.
*   **Backpressure:** Automatic handling of slow receivers (Queue Lagging detection).

### 4. The Type Shield (Schema Enforcement)
Optional strict typing for your agent's memory using **Pydantic**.
*   Integrates deeply with the Transaction engine.
*   Prevents "Memory Corruption" by validating state transitions before commit.
*   **Overhead:** Negligible (~8 microseconds per write).

### 5. Workflow Engine Upgrade
*   **Flux DSL 2.0:** Support for `if/else`, `while` loops, and `nested flows` directly in YAML.
*   **Performance:** ~0.5ms scheduling overhead per step.

---

## 📉 Performance Benchmarks

| Metric | Target | Result | Improvement |
| :--- | :--- | :--- | :--- |
| **Signal Throughput** | 100k eps | **2,715,554 eps** | **27x** |
| **Context Overhead** | < 5 µs | **0.70 µs** | Acceptable |
| **Memory Safety** | Zero Copy | **Verified** | 0.01MB delta on 100MB load |

---

## ⚠️ Breaking Changes

*   **Python < 3.14 Dropped:** Theus v3 requires Python 3.14 for Sub-interpreter support.
*   **Legacy API Removed:** `BaseContext.register_process` is removed. Use `TheusEngine.register`.
*   **Context Immutability:** You cannot mutate context fields directly (`ctx.x = 1` raises Error). You MUST use `ctx = ctx.update(x=1)`.

---


### 6. The Workflow Control Paradigm Shift
Theus V3 introduces a fundamental change in how agents and workflows are controlled, moving away from legacy "Python FSMs" towards a dual-layer architecture:

#### A. Macro-Control: The Flux Engine (Data-Driven FSM)
We have deprecated the Python `WorkflowManager` (State Machine) in favor of **Flux DSL**.
*   **Old Way:** Defining `states` and `transitions` in YAML, managed by Python.
*   **New Way:** Using `flux: while` and `flux: if` to create **Data-Driven Loops**.
*   **Why?**
    *   **Resilience:** State is persisted in `Context`. If the system crashes, it recovers exactly where it left off.
    *   **Performance:** The loop runs in Rust, bypassing the Python GIL for control logic.

#### B. Micro-Control: The Pipeline Pattern
We have actively prohibited "Nested Engine Calls" (calling `engine.execute_workflow` inside a process).
*   **Problem:** Nested calls in the Rust Multi-threaded core cause **Deadlocks** (Re-entrant Lock contention) and massive 100x overhead.
*   **Solution:** The **Pure Python Pipeline Pattern**.
    *   Complex inner loops (like Agent Deliberation or Math Heavy Steps) should be composed as **Pure Python Functions**.
    *   These pipelines run as a *single* Atomic Process from the Engine's perspective.
*   **Impact:**
    *   **Zero Overhead:** Inner loops run at native Python speed.
    *   **Deadlock Free:** The Engine lock is held once for the entire pipeline duration.

#### C. GUI Integration Constraint (Background Worker Required)
Theus V3 `execute_workflow` is a **Run-to-Completion** (Blocking) operation designed for maximum throughput. It does **NOT** support "Tick-based" execution (common in Legacy FSMs).
*   **Constraint:** You cannot run Theus directly on a GUI Main Thread (e.g., PyQt/Tkinter), as it will freeze the interface.
*   **Pattern:** You MUST run Theus in a **Background Worker Thread**. The GUI should act as an *Observer*, polling the Thread-Safe Context for updates.

> **Philosophy Note (POP Principle 2.3 & 1.3):**
> This architecture embodies a conscious trade-off. We prioritize **High-Level Transparency** in the Workflow (Macro) while allowing **Pragmatic Performance** in the Pipeline (Micro).
> A complex calculation (e.g., 100 math ops) is semantically *one step* ("Think"), and thus should be implemented as *one process*, keeping the Workflow Map clean and the Execution fast.


---

## 📦 Installation

```bash
pip install theus==3.0.0
```

*Required: Rust toolchain (if building from source).*
