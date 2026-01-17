# 🧭 Theus Documentation Map (v3.0)

> **Welcome to Theus!** This framework is vast, covering everything from high-level AI philosophy to low-level Rust memory management. To avoid getting lost, please choose the **Persona** that best fits your current goal.

---

## 🤖 Persona 0: The AI Assistant
**Goal:** "I am an AI coding assistant and need to understand Theus quickly to help users."

*   **Start Here:** [**AI Quick Reference (Cheat Sheet)**](./tutorials/ai/00_QUICK_REFERENCE.md)
    *   *Time:* 5 mins
    *   *Outcome:* Copy-paste patterns for common tasks.
*   **Full Guide:** [**AI Tutorials (7 Modules)**](./tutorials/ai/)
    *   *Covers:* Core Concepts, Contracts, Engine, Flux DSL, Audit, Advanced.

---

## 🚀 Persona 1: The AI Developer
**Goal:** "I want to build an Agent *now*. I don't care about memory zones or Rust macros yet."

*   **Start Here:** [**AI Developer Guide (Quickstart)**](./AI_DEVELOPER_GUIDE.md)
    *   *Time:* 15 mins
    *   *Outcome:* A running Hello World agent.
*   **Reference:** [**Chapter 1: Introduction**](./tutorials/en/Chapter_01.md)

---

## 🏗️ Persona 2: The System Architect
**Goal:** "I need to understand how Theus ensures reliability. How does the Rust Core work? What is POP?"

*   **Theory:** [**POP Whitepaper v2.0 (Foundational)**](./POP_Whitepaper_v2.0.md)
    *   *Concepts:* 3-Axis Context, Strict Mode, Neural Darwinism.
*   **Design:** [**SPECS (Technical Specifications)**](./SPECS/)
    *   *Concepts:* Rust Microkernel, Tiered Guards, Zero-Copy Heavy Zone.
*   **Philosophy:** [**The POP Manifesto**](./POP_Manifesto.md)
    *   *Concepts:* "Data is Inert", "Process is Logic".

---

## 🎓 Persona 3: The Learner / Contributor
**Goal:** "I want to master Theus from the ground up or contribute to the core."

**Phase 1: Foundations (Python Layer)**
1.  [**Chapter 1: The First Process**](./tutorials/en/Chapter_01.md)
2.  [**Chapter 2: Context & Zones**](./tutorials/en/Chapter_02.md)
3.  [**Chapter 3: The Contract (@process)**](./tutorials/en/Chapter_03.md)
4.  [**Chapter 4: TheusEngine**](./tutorials/en/Chapter_04.md)

**Phase 2: Advanced Orchestration**
5.  [**Chapter 11: Workflow Flux DSL**](./tutorials/en/Chapter_11.md) ⭐ (Major v3.0 update)
6.  [**Chapter 10: Heavy Zone Optimization**](./tutorials/en/Chapter_10.md)

**Phase 3: Internals**
7.  [**SPECS/12: Engine Runtime**](./SPECS/12_Engine_Runtime.md)
8.  [**Release Notes v3.0.0**](../RELEASE_NOTES_v3.0.0.md)

---

## 📂 Documentation Structure

```
Documents/
├── tutorials/
│   ├── ai/          # 🆕 AI-optimized tutorials (7 modules)
│   └── en/          # Human tutorials (16 chapters)
├── SPECS/           # Technical specifications (13 files)
├── AI_DEVELOPER_GUIDE.md
├── POP_Manifesto.md
└── POP_Whitepaper_v2.0.md
```

---

> **Note on v3.0:** All documentation has been updated for Theus v3.0.0 with Flux DSL workflow, `domain_ctx.*` paths, and new API.
