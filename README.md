# Theus Framework

[![PyPI version](https://badge.fury.io/py/theus.svg)](https://badge.fury.io/py/theus)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)

> *"Safe architecture for AI-assisted development. Powered by Rust."*

---

## 🧭 **Where do I start?**

Theus is vast. Use our **[Interactive Documentation Map](https://github.com/dohuyhoang93/theus/blob/main/Documents/00_Start_Here_Map.md)** to find your path:
*   🚀 **I want to build an Agent now:** [Go to Quickstart](https://github.com/dohuyhoang93/theus/blob/main/Documents/AI_DEVELOPER_GUIDE.md)
*   🤖 **I am an AI Assistant:** [Go to AI Tutorials](https://github.com/dohuyhoang93/theus/blob/main/Documents/tutorials/ai/00_QUICK_REFERENCE.md)
*   🏗️ **I want to check architecture:** [Go to Specs](https://github.com/dohuyhoang93/theus/blob/main/Documents/SPECS/)
*   🎓 **I want to learn from scratch:** [Go to Tutorials](https://github.com/dohuyhoang93/theus/blob/main/Documents/tutorials/en/Chapter_01.md)

---

## � Why Theus?

> **"Build with confidence. Your AI assistant writes the code—Theus makes sure it's safe."**

Whether you're **vibe coding** with an AI assistant, building a complex agent, or crafting production software that needs to last for years—Theus has your back.

### For Vibe Coders & AI-Assisted Development
You focus on *what* you want to build. Let your AI write the logic. Theus automatically ensures:
- Every function declares exactly what data it reads and writes
- No hidden side effects or surprise mutations
- If something goes wrong, it rolls back cleanly

### For Teams Who Care About Maintainability
Come back to your code in 2 years. You'll thank yourself:
- **Explicit Contracts:** Every `@process` is self-documenting
- **Transparent State:** Know exactly where your data lives and who can touch it
- **Built-in Audit:** Validate business rules at the boundary, not scattered in code

### For Safety-Critical Applications
When bugs aren't just annoying—they're costly:
- **Transaction Safety:** Automatic rollback on failure
- **Explicit Access:** Processes must declare every data point they touch via `@process` contracts
- **Industrial Audit:** Block, warn, or stop based on configurable rules

---

## 📦 Installation

Theus v3.0 requires **Python 3.14+** to leverage Sub-interpreter support.

```bash
pip install theus
```

---

## ⚡ Quick Start

### Option 1: Use a Template (Recommended)

```bash
# Create a new project with the E-Commerce demo (full-featured)
py -m theus.cli init my_app --template ecommerce
cd my_app
python main.py
```

This creates a complete runnable demo with: Orders, Payments, Heavy Zone, Audit Rules, and Workflow.

### Option 2: Manual Setup

```python
from theus import TheusEngine, process

# 1. Define a Process with Contract
@process(
    inputs=['domain.accounts'],
    outputs=['domain.accounts'],
    errors=['ValueError']
)
def transfer(ctx, from_user: str, to_user: str, amount: int):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    # V3 Pattern: Copy -> Modify -> Return
    # ctx.domain.accounts is Immutable (FrozenDict) in strict_mode
    accounts = dict(ctx.domain.accounts)
    
    if accounts.get(from_user, 0) < amount:
        raise ValueError("Insufficient funds")
    
    accounts[from_user] -= amount
    accounts[to_user] = accounts.get(to_user, 0) + amount
    
    # Return new state (Engine handles the commit)
    return accounts

# 2. Initialize Engine
from src.context import DemoSystemContext
engine = TheusEngine(DemoSystemContext(), strict_mode=True)
engine.register(transfer)

# 3. Execute with Transaction Safety
result = engine.execute(transfer, from_user="Alice", to_user="Bob", amount=500)
```

> 💡 **Available Templates:** `standard`, `ecommerce`, `hybrid`, `agent`, `minimal`
> Run `py -m theus.cli init --help` to see all options.

---

## 🔄 Workflow: Flux DSL

v3.0 introduces **Flux DSL** - a declarative YAML language for workflow control.

```yaml
# workflows/main.yaml
steps:
  - process: "initialize"
  
  - flux: if
    condition: "domain['is_valid'] == True"
    then:
      - "process_data"
      - "save_result"
    else:
      - "handle_error"
  
  - flux: while
    condition: "domain['items_left'] > 0"
    do:
      - "process_next_item"
```

Execute with:
```python
engine.execute_workflow("workflows/main.yaml")
```

---

## 🛠️ CLI Tools

Theus provides a powerful CLI suite to accelerate development and maintain architectural integrity.

*   **`py -m theus.cli init <project_name>`**: Scaffolds a new project with the standard V3 structure.
*   **`py -m theus.cli audit gen-spec`**: Scans your `@process` functions and automatically populates `specs/audit_recipe.yaml`.
*   **`py -m theus.cli audit inspect <process_name>`**: Inspects the effective audit rules for a process.
*   **`py -m theus.cli schema gen`**: Generates `specs/context_schema.yaml` from your Python Dataclass definitions.
*   **`py -m theus.cli check`**: Runs the **POP Linter** to enforce architectural purity.

---

## 🧠 Advanced Architecture

### The Transaction Engine (v3.0)
Theus prioritizes **Performance** (Zero-Copy) while providing **Safety Tools**:
*   **Zero-Copy Reads:** Reading data is O(1) direct memory access.
*   **Copy-on-Write:** To modify data, you **MUST** create a copy (`new = list(old)`). 
*   **Atomic Commit:** The Engine swaps the pointer to the new data only if the transaction succeeds.
> ⚠️ **Warning:** In-place mutation (e.g., `list.append`) bypasses the safety lawyer. Always use the Copy-on-Write pattern.

### The Heavy Zone (Optimization)
For AI workloads (Images, Tensors) > 1MB, use `heavy_` variables.
*   **Behavior:** Writes bypass the Transaction Log (Zero-Copy).
*   **Trade-off:** Changes to Heavy data are **NOT** reverted on Rollback.

### 🚀 High Performance Training
For Pure Training Loops where Transaction safety is overkill:
```python
engine = TheusEngine(sys_ctx, strict_mode=False)
```
*   **Effect:** Completely disables Rust Transaction Layer (Zero Overhead).
*   **Performance:** Native Python execution speed.

---

## 📚 Documentation

*   **[POP Manifesto](https://github.com/dohuyhoang93/theus/blob/main/Documents/POP_Manifesto.md):** The philosophy behind Process-Oriented Programming.

---

## ⚖️ License

*   **Software:** [MIT License](https://opensource.org/licenses/MIT).
*   **Whitepaper:** [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**Maintained by:** [Hoàng Đỗ Huy](https://github.com/dohuyhoang93)