# RELEASE NOTES - Theus v2.1.0

> **Code Name**: "Theus Framework"
> **Release Date**: 2025-12-19

Theus v2.1 marks the official transition from "POP SDK" to **Theus Agentic Framework**. It introduces a complete architectural overhaul, industrial-grade audit capabilities, and a standardized "3-Axis Context" design.

---

## 🌟 Highlights

### 1. Theus Microkernel Architecture
The core engine (`TheusEngine`) is now separated from the implementation layers. It enforces strict bounds via the **ContextGuard** and **Transaction Manager**.
- **Refactoring:** Renamed `POPEngine` to `TheusEngine` (with backward compatibility).
- **Safety:** New `strict_mode=True` (Vault Mode) protects context from unlicensed modification.

### 2. 3-Axis Context Design
Context is now modeled as a 3D coordinate system:
- **Layer Axis:** Global / Domain / Local.
- **Semantic Axis:** Input / Output / Side-Effect / Error.
- **Zone Axis:** Data (Persisted) / Signal (Transient) / Meta (Diagnostic).

### 3. Industrial Audit System V2
A robust audit pipeline inspired by Industrial Control Systems (ICS):
- **Input Gate:** Validates data *before* entering the process.
- **Output Gate (Shadow Audit):** Validates mutations *before* commit.
- **Cycle Reset:** Supports "Warning -> Reset" lifecycle for monitoring.
- **Traceability:** Rule violations now support custom human-readable messages.

### 4. Developer Experience (DX)
- **CLI (`theus`):** New `init` command to scaffold projects. `audit` and `schema` tools included.
- **Orchestration:** Enhanced FSM with explicit `events` handling.
- **Documentation:** Completely restructured into `Architecture` (Theory) and `Handbook` (Practice).

---

## 🛠 Breaking Changes

- **Renaming:** `POPEngine` is deprecated. Use `TheusEngine`.
- **Context Structure:** Recommended migration to `dataclasses` instead of `pydantic.BaseModel` for Core Contexts to support finer granular locking.
- **CLI:** `pop` command alias is removed. Use `theus`.

## 📦 Installation

```bash
pip install theus==2.1.0
```

## 📚 Documentation

See `Documents/Architecture` and `Documents/Handbook` for details.
