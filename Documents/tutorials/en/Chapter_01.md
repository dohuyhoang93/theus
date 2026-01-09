# Chapter 1: Theus v2 - The Era of Process-Oriented Programming (POP)

## 1. The Philosophy of Theus: "Zero Trust" State Management
In modern software development (AI Agents, Automation, Banking), the biggest challenge is the chaos of State Management. Data mutates uncontrollably, Events are mixed with persistent Data, leading to non-deterministic bugs that are impossible to reproduce.

**Theus v2 (Rust Core)** is not just a library; it is a **Process Operating System** for your code, enforcing the **3-Axis Context Model**:
1.  **Layer:** Where does the data live? (Global/Domain/Local).
2.  **Semantic:** What is the data used for? (Input/Output).
3.  **Zone:** How is the data guarded? (Data/Signal/Meta/Heavy).

## 2. Why POP v2?
Traditional models (OOP, FP) lack a crucial piece: **Runtime Architectural Control.**
- **OOP:** Good encapsulation, but Data Flow is hidden within methods.
- **Theus POP:** Complete separation:
    - **Context:** A "static" data repository, strictly zoned.
    - **Process:** "Stateless" functions that can only touch the Context via a strict **Contract**.

## 3. Key Components of Theus v2.2
1.  **Rust Engine (Theus Core):** The coordination brain, integrating the Transaction Manager and Lock Manager with zero-overhead.
2.  **Hybrid Context:** Intelligent storage that automatically classifies Data, Signals, and **Heavy Assets** (Tensors/Blobs).
3.  **Audit System:** The traffic police, blocking transactions that violate business rules (Rule-based Enforcement).
4.  **Workflow Flux:** The conductor coordinating flow based on events (Declarative YAML).

## 4. Installation
Theus v2 requires Python 3.10+ and integrates deeply with **Pydantic** for validation.

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
