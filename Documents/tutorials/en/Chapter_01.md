# Chapter 1: Theus v3.0 - The Era of Process-Oriented Programming (POP)

## 1. The Philosophy of Theus: "Zero Trust" State Management
In modern software development (AI Agents, Automation, Banking), the biggest challenge is the chaos of State Management. Data mutates uncontrollably, Events are mixed with persistent Data, leading to non-deterministic bugs that are impossible to reproduce.

**Theus v3.0 (Rust Microkernel)** is not just a library; it is a **Process Operating System** for your code, enforcing the **3-Axis Context Model**:
1.  **Layer:** Where does the data live? (Global/Domain/Local).
2.  **Semantic:** What is the data used for? (Input/Output).
3.  **Zone:** How is the data guarded? (Data/Signal/Meta/Heavy).

## 2. Why POP v3?
Traditional models (OOP, FP) lack a crucial piece: **Runtime Architectural Control.**
- **OOP:** Good encapsulation, but Data Flow is hidden within methods.
- **Theus POP:** Complete separation:
    - **Context:** A "static" data repository, strictly zoned.
    - **Process:** "Stateless" functions that can only touch the Context via a strict **Contract**.

> **🧠 Philosophy Note:** This separation stems from Principle 1.1 of the [POP Manifesto](../../POP_Manifesto.md): **"Data is Inert, Process is Logic."** By stripping data of behavior (no methods on objects), we eliminate hidden side effects.

## 3. Key Components of Theus v3.0
1.  **Rust Engine (Theus Core):** The coordination brain, integrating the Transaction Manager and Lock Manager with zero-overhead.
2.  **Hybrid Context:** Intelligent storage that automatically classifies Data, Signals, and **Heavy Assets** (Tensors/Blobs).
3.  **Audit System:** The traffic police, blocking transactions that violate business rules (Rule-based Enforcement).
4.  **Flux DSL:** The workflow engine coordinating flow based on YAML definitions (if/while/run).
5.  **SignalHub:** High-throughput Tokio-powered event system (2.7M+ events/sec).

## 4. What's New in v3.0 (Breaking Changes)

| v2.2 | v3.0 | Notes |
|:-----|:-----|:------|
| Python 3.10+ | **Python 3.14+** | Sub-interpreter support |
| `domain.*` paths | `domain_ctx.*` paths | Strict Rust checking |
| `engine.run_process()` | `engine.execute()` | New API |
| FSM (states/events) | **Flux DSL** (if/while/run) | Complete workflow rewrite |
| WorkflowManager | **WorkflowEngine** (Rust) | Deprecated Python FSM |

## 5. Installation
Theus v3.0 requires **Python 3.14+** to leverage Sub-interpreter support.

### Option 1: User (Production)
```bash
pip install theus
```

### Option 2: Developer (Source)
We use **Maturin** to build the Rust Core.

```bash
# 1. Install Maturin
pip install maturin

# 2. Build & Install (Dev Mode)
# This compiles the Rust Core and installs it in your venv
maturin develop
```

---
**Exercise Chapter 1:**
Forget the old way of coding. Imagine your system is a factory.
- What are the raw materials (Input)?
- What are the products (Output)?
- What are the sirens/alarms (Signal)?
- What are the heavy raw materials like steel beams (Heavy)?
In Chapter 2, we will build the "warehouse" (Context) for this factory.
