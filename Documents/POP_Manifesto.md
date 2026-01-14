# 🟦 **POP MANIFESTO — The Process-Oriented Programming Manifesto**

> [🇻🇳 Đọc bản Tiếng Việt (Vietnamese Version)](./POP_Manifesto_VN.md) 

This manifesto fully embodies:

*   The philosophy of thinking
*   The philosophy of design
*   The philosophy of architecture
*   The principles of operation
*   The developer's commitment
    and **the core functions distinguishing POP from OOP, FP, and Clean Architecture**.

---

## 🌐 **Preface**

Process-Oriented Programming (POP) is a programming philosophy that places the **Process** at the center, replacing objects, pure functions, or modules.

POP does not aim to compete with OOP or FP, but to provide a **transparent, pragmatic, and maintainable** path for every system – from simple to complex – by modeling the **operational logic of the system** as **sequential steps that are easy to read, control, explain, and prove**.

POP is the fusion of **human reasoning**, **a simple mathematical-mental model**, and **engineering design discipline**.

POP states:

> "Every system is a flow of data passing through a sequence of well-defined processes. Model the system using that very flow."

---

## 🟦 **1. Core Philosophy**

### **1.1. Programming is Modeling the Flow**

Every piece of software – from robots, PLCs, AI, to backends – is a **sequence of intentional actions**.

A **Process** is the most natural form to describe an action.

POP views the system as a **flow**:

```
Input Data → Transform → Check → Decide → Act → Output Data
```

Everything is modeled into **clearly named steps**, not hiding logic inside classes, not stuffing behavior into data, and not embedding conditions into ambiguous structures.

---

### **1.2. Transparency is the Ultimate Value**

> "If it cannot be explained, it is not allowed to be implemented."

POP places **explainability** above all else:

*   Each process must be describable by **a single sentence with Subject – Verb – Object**.
*   Every change in the context must have a clear domain reason.
*   Every step in the workflow must be readable like a job description.

NOT accepted:

*   Logic buried under vague abstraction layers.
*   Data models pushed into "god object" types.
*   Secret behaviors hidden in objects or callbacks.

Transparency is Safety.
Transparency is Maintainability.
Transparency is Humanity in Software.

---

### **1.3. Avoid Binary Extremes – Embrace Non-Duality**

POP does not pursue:

*   "Pure function or nothing"
*   "Immutable context or totally broken"
*   "One step – one line of code"
*   "Workflows must be linear"

POP asserts:

> "The world is not binary, and neither is software."

POP allows:

*   Controlled mutation.
*   Branching within a process if transparent.
*   Large processes if they represent a semantic block.
*   Parallel steps if easy to explain.
*   Dynamic workflows if safety rules exist.

What matters is not size or purity.
What matters is **precise semantics and verifiability**.

---

### **1.4. Data Has No Behavior – Context Must Not "Know How To Do"**

Context is:

*   The data flow passing through the workflow.
*   The center for storing domain state.
*   The "state of the simulated world".

But Context **must not contain behavior**, must not contain logic, and must not self-mutate.

Context is "inert data", but not stupid data.
It is the **current state of the system**, not a place to hide actions.

---

## 🟦 **2. Design Philosophy**

### **2.1. Process is the Smallest Unit of Design**

No classes, no objects, no methods hiding logic.
POP uses the **Process** as the fundamental unit:

```
process(context) → new_context
```

A Process must:

*   Do **one meaningful thing**.
*   Not break the domain.
*   Have clear inputs/outputs (read/write context).
*   Be testable via unit tests.
*   Be easily describable in words.

---

### **2.2. Workflow is Where Architecture is Visible**

The Workflow represents:

*   The flow of work.
*   Branching.
*   Parallelism.
*   Result aggregation.
*   Loops.
*   Trial-and-failure (retry, fallback, compensation).

The Workflow is the **Map of the System**.
Anyone can read it, no programming knowledge required.

---

### **2.3. Decompose Processes by Semantics, Not Line Count**

Rules:

*   A process contains **one meaning**, which may consist of multiple small steps.
*   Do not force processes to be extremely small.
*   Do not allow processes to be so large that they are hard to explain.

---

### **2.4. Reuse is Secondary, Transparency is Primary**

POP accepts code duplication if:

*   It helps transparency.
*   It reduces coupling.
*   It reduces layers and layers of abstraction.

POP opposes "over-generalization", because generic code often hides semantics.

---

## 🟦 **3. Architectural Philosophy**

### **3.1. The 3-Axis Context Model**

Context is no longer flat. It is a 3-dimensional space optimizing safety and performance:

*   **Layer (Scope)**: Global (Config), Domain (Business), Local (Ephemeral).
*   **Zone (Policy)**: Data (Persistent), Signal (Transient), Meta (Debug), Heavy (Zero-Copy).
*   **Semantic (Role)**: Input (Read-only), Output (Read-Write).

-> *Goal: Comprehensive control over the data lifecycle.*

---

### **3.2. Process-Safe Context Evolution**

Context must evolve in a controlled manner:

*   Every change must be observable.
*   Never write implicitly.
*   Never reuse fields for different meanings.
*   Domain fields must have fixed meanings.

---

### **3.3. Control Flow: From Linear to Reactive**

POP evolves beyond static graphs to embrace **Finite State Machines (FSM)** and **Reactive Rules** for complex dynamic systems:

*   **Declarative**: Flow is defined in configuration, preventing logic coupling in code.
*   **Reactive**: Execution is triggered by explicit Events.
*   **Traceable**: Whether linear or reactive, the path of execution must always be deterministically traceable.

---

### **3.4. POP Does Not Oppose OOP or FP – It Chooses Pragmatism**

POP learns from FP:

*   Controlled purity.
*   Local immutability.
*   Avoidance of unwanted side-effects.

POP learns from OOP:

*   Modularity.
*   Grouping by domain.

POP learns from Clean Architecture:

*   Separation of domain and adapter.
*   Unidirectional dependency.

But POP is not rigid.
POP places the Process at the center instead of the Class or the Pure Function.

---

## 🟦 **4. Operational Philosophy**

### **4.1. Software is Work – Describe It Like Work**

POP Workflows are written in natural language:

```yaml
- call: "camera.capture_photo"
- call: "image.find_object"
- if: ctx.object.found
    then:
      - call: "robot.pick_up"
```

No abbreviations.
No programming symbols.
No hard-to-remember syntax.

---

### **4.2. Every Step is Auditable**

POP ensures that:

*   Before each process: Snapshot context.
*   After each process: Snapshot context.
*   Delta must be transparent.

Helps control errors, control behavior, and serve industrial safety.

---

### **4.3. Process is Easy to Test – Workflow is Easy to Verify**

*   Process has clear Input → Output.
*   Workflow can run in simulation.
*   The entire system can be "stepped-through".

---

## 🟦 **5. The POP Practitioner's Commitment**

I commit:

1.  To not hide logic.
2.  To not stuff behavior into data.
3.  To not create messy abstractions.
4.  To not break the domain context for convenience.
5.  To not be extreme about purity or mutability.
6.  To always be able to explain every step of the system.
7.  To prioritize clarity over technical flashiness.
8.  To write software for real humans to understand.
9.  To control change with reason, not by habit.
10. To respect the natural flow of data and logic.

---

## 🟦 **6. Final Statement**

**POP is the method of placing humans at the center of programming thinking.**

*   Humans think in steps → POP models in steps.
*   Humans understand things through actions → POP models actions through processes.
*   Humans perceive flow → POP organizes systems by context flow.

POP is not just a technique.
POP is a **perspective on clarity and honesty in software**.
