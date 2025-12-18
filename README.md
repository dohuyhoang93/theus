# Theus (formerly POP SDK)

**The "Operating System" for AI Agents and Complex Systems.**

[![PyPI version](https://badge.fury.io/py/theus.svg)](https://badge.fury.io/py/theus)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Theus (Process-Oriented Programming)** is a paradigm shift designed for building robust, stateful AI agents. Unlike OOP which encapsulates state and behavior, Theus **decouples** them completely to ensure:
1.  **Transactional Integrity**: Every action is atomic.
2.  **Safety by Default**: Inputs are immutable; outputs are strictly contracted.
3.  **Observability**: Every state change is logged and reversible.

---

## 🌟 Key Features

# Theus SDK (V2.1)

> **Process-Oriented Programming (POP) SDK for Industrial Agents**
> *Formerly known as POP SDK*

Theus is a robust, clean-architecture framework for building deterministic, auditable, and resilient AI Agents. It implements the **POP Microkernel Architecture**, separating Data (Context) from Behavior (Process) and Orchestration (Workflow).

## 🚀 What's New in V2.1?

- **Microkernel Core**: Separated `POPEngine` from Orchestration Logic.
- **Hybrid Workflow**: Combine Finite State Machines (FSM) with Linear Process Chains.
- **Thread-Safe Concurrency**: `ThreadExecutor` for non-blocking I/O and background tasks.
- **Industrial Safety**:
    - **ContextGuard**: Prevents unauthorized memory mutations.
    - **Transaction Rollback**: Atomically reverts state on process crash.
    - **Audit System**: Runtime validation of Inputs/Outputs via Gates.
- **CLI**: Rapidly scaffold projects with `theus init`.

## 📚 Documentation

- [Architecture Specification (V2.1)](Documents/SPECS/theus_v2_1_architecture.md)
- [Configuration Guide (Workflow & Audit)](Documents/GUIDES/configuration.md)
- [RELEASE NOTES (v0.2.0)](RELEASE_NOTES_v0.2.0.md)

## 🛠 Installation

```bash
pip install theus
```

## ⚡ Quick Start

Create a fully functional showcase project:
```bash
# 1. Create Skeleton
theus init MyProject

# 2. Run Demo
cd MyProject
python main.py
```
Interact with the CLI:
`start` (Run Workflow), `hack` (Test Security), `crash` (Test Resilience), `rollback` (Test Transactions).

---

## 🚀 Quick Start (CLI)

The fastest way to start is using the CLI tool.

> **Note**: We recommend using `python -m theus` to ensure compatibility across all operating systems.

```bash
# 1. Initialize a new project
python -m theus init my_agent

# 2. Enter directory
cd my_agent

# 3. Run the skeleton agent
python main.py
```

Arguments:
- `python -m theus init <name>`: Create a new project folder.
- `python -m theus init .`: Initialize in current directory.

---

---

## 🛠️ Advanced CLI Tools

Beyond initialization, Theus provides tools for Audit & Schema management.

### Audit Generation
Start from code, generate the rules.

```bash
python -m theus audit gen-spec
```

### Schema Generation
Generate Context Schema from your Pydantic models.

```bash
python -m theus schema gen --context-file src/context.py
```

---

## 📚 Manual Usage

### 1. Define Context (Data)
Using Pydantic V2. Theus V2 introduces **Hybrid Context Zones** (Data, Signal, Meta) via naming conventions.

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from theus import BaseSystemContext

class AppGlobal(BaseModel):
    # [DATA ZONE] Immutable Configuration
    app_name: str = "MyAgent"

class AppDomain(BaseModel):
    # [DATA ZONE] Business State (Persisted)
    user_id: str = ""
    status: str = "IDLE"

    # [SIGNAL ZONE] Transient Events (Prefix: sig_ or cmd_)
    sig_stop: bool = False
    
    # [META ZONE] Diagnostics (Prefix: meta_)
    meta_last_error: Optional[str] = None

class MySystem(BaseSystemContext):
    def __init__(self):
        self.global_ctx = AppGlobal()
        self.domain_ctx = AppDomain()
```

### 2. Define Process (Logic)
Declarative contracts now support **4 Semantic Axes**: Input, Output, Side-Effect, Error.

```python
from theus import process

@process(
    inputs=['domain.user_id'], 
    outputs=['domain.status', 'domain.meta_last_error'],
    side_effects=['I/O'],      # New in V2: Declarative Side-Effect
    errors=['ValueError']      # New in V2: Expected Errors
)
def check_user(ctx):
    try:
        # Valid: Declared in outputs
        ctx.domain_ctx.status = "CHECKING"
        # ... perform DB check ...
        return "Checked"
    except ValueError as e:
        ctx.domain_ctx.meta_last_error = str(e)
        raise e
```

### 3. Run Engine
```python
from theus import POPEngine

system = MySystem()
engine = POPEngine(system) # Default: Warning Mode

engine.register_process("check_user", check_user)
engine.run_process("check_user")
```

---

## ⚙️ Configuration

You can control strictness via Environment Variables (supported in `.env` files):

| Variable | Values | Description |
|----------|--------|-------------|
| `THEUS_STRICT_MODE` | `1`, `true` | **Crash on Violation**: External code (Main Thread) cannot modify Context directly. |
| | `0`, `false` | **Log Warning**: External code can modify context, but it logs a `LockViolationWarning`. |

### Why Strict Mode? (The Vault)
Theus enforces **Context Integrity**. 
- In **Strict Mode (`1`)**, the Context is "Vaulted". Only registered Processes can modify it. Any attempt to modify `ctx.domain` from `main.py` without using `engine.edit()` will raise an error and **crash the agent**. This is recommended for Production/CI to prevent "State Spaghetti".
- In **Warning Mode (`0`)**, violations are logged but permitted. This is useful for rapid prototyping.

(Legacy `POP_STRICT_MODE` is also supported for backward compatibility).

### Safe External Mutation
To modify context from `main.py` without triggering warnings/errors, use the explicit API:

```python
with engine.edit() as ctx:
    ctx.domain.my_var = 100
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
