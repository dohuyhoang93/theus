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

### 🛡️ Safety & Security
- **Context Locking ("The Vault")**: Prevents accidental state mutation from external code (`main.py`). Warning mode by default, Strict mode (crash) for CI.
- **Frozen Inputs**: Process inputs are wrapped in `FrozenList`/`FrozenDict`. Side-effects are blocked at runtime.
- **Strict Contracts**: Explicit `@process(inputs=[...], outputs=[...])` decorators prevent "State Spaghetti".

### ⚡ Developer Experience
- **POP CLI**: Bootstrap new projects instantly with `pop init`.
- **Hybrid Guard**: Friendly warnings for rapid dev, Strict enforcement for interaction.
- **Zero-Dependency Core**: Pure Python. Compatible with PyTorch, TensorFlow, or any other library.

---

## 📦 Installation

```bash
pip install theus
```

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
Using Pydantic V2 for robust verification.

```python
from pydantic import BaseModel

class MyGlobal(BaseModel):
    counter: int = 0

class MySystem(BaseModel):
    global_ctx: MyGlobal
    # ... domain_ctx ...
```

### 2. Define Process (Logic)
```python
from theus import process

@process(
    inputs=['global.counter'], 
    outputs=['global.counter']
)
def increment(ctx):
    # Valid: Declared in outputs
    ctx.global_ctx.counter += 1
    return "Incremented"

@process(inputs=['global.counter'], outputs=[])
def illegal_write(ctx):
    # INVALID: Read-Only Input
    # Raises ContractViolationError
    ctx.global_ctx.counter += 1 
```

### 3. Run Engine
```python
from theus import POPEngine

system = MySystem(global_ctx=MyGlobal())
engine = POPEngine(system) # Default: Warning Mode

engine.register_process("inc", increment)
engine.run_process("inc")
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
