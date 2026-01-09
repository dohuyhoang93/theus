# Theus: Process-Oriented Operating System for Python

[![PyPI version](https://img.shields.io/pypi/v/theus.svg)](https://pypi.org/project/theus/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Paper License: CC-BY 4.0](https://img.shields.io/badge/Paper--License-CC--BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

> **"Data is the Asset. Code is the Liability. Theus protects the Asset."**

Theus is a next-generation architectural framework that treats your application not as a collection of objects, but as a **deterministic workflow of processes**. It introduces the **Process-Oriented Programming (POP)** paradigm to solve the chaos of state management in complex systems like AI Agents, Core Banking, and Industrial Automation.

---

## 🌪️ The Problem
In modern software (OOP, EDA, Microservices), the biggest source of bugs is **State Management**:
*   **Implicit Mutations:** Who changed `user.balance`? Was it the PaymentService or the RefundHandler?
*   **Race Conditions:** Transient events corrupting persistent data.
*   **Zombie State:** Old references pointing to stale data.
*   **Audit Gaps:** We log *what* happened, but we can't mathematically prove *why* it was allowed.

## 🛡️ The Theus Solution
Theus acts as a micro-kernel for your logic, enforcing strict architectural invariants at runtime:

### 1. The 3-Axis Context Model
State is no longer a "bag of variables". It is a 3D space defined by:
*   **Layer:** `Global` (Config), `Domain` (Session), `Local` (Process).
*   **Semantic:** `Input` (Read-only), `Output` (Write-only), `SideEffect` (env), `Error`.
*   **Zone:**
    *   **DATA:** Persistent Assets (Replayable).
    *   **SIGNAL:** Transient Events (Reset on Read).
    *   **META:** Observability (Logs/Traces).
    *   **HEAVY:** High-Perf Tensors/Blobs (Zero-Copy, Non-Transactional).

```
                                     [Y] SEMANTIC
                             (Input, Output, SideEffect, Error)
                                      ^
                                      |
                                      |
                                      |                +------+------+
                                      |               /|             /|
                                      +--------------+ |  CONTEXT   + |----------> [Z] ZONE
                                     /               | |  OBJECT    | |      (Data, Signal, Meta, Heavy)
                                    /                | +------------+ |
                                   /                 |/             |/
                                  /                  +------+------+
                                 v
                            [X] LAYER
                     (Global, Domain, Local)
```

### 2. Zero-Trust Memory
*   **Default Deny:** Processes cannot access ANY data unless explicitly declared in a `@process` Contract.
*   **Immutability:** Inputs are physically frozen (`FrozenList`, `FrozenDict`).
*   **Isolation:** Signals cannot be used as Inputs for Business Logic (Architectural Boundary enforcement).

### 3. Industrial-Grade Audit
*   **Active Defense:** Rules (`min`, `max`, `regex`) are enforced at Input/Output Gates.
*   **Severity Levels:**
    *   **S (Safety):** Emergency Stop.
    *   **A (Abort):** Hard Stop Workflow.
    *   **B (Block):** Rollback Transaction.
    *   **C (Campaign):** Warning.
*   **Resilience:** Configurable tolerance thresholds (e.g., "Allow 2 glitches, block on 3rd").

---

## 📦 Installation

Theus requires **Python 3.12+** to leverage advanced typing and dataclasses.

```bash
pip install theus
```

---

## ⚡ Quick Start: Building a Bank

This example demonstrates Contracts, Zoning, and Transaction safety.

### 1. Define the Context (The Asset)
```python
from dataclasses import dataclass, field
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class BankDomain(BaseDomainContext):
    # DATA ZONE: Persistent Assets
    accounts: dict = field(default_factory=dict) # {user_id: balance}
    total_reserves: int = 1_000_000
    
    # SIGNAL ZONE: Control Flow
    sig_fraud_detected: bool = False

@dataclass
class BankSystem(BaseSystemContext):
    domain_ctx: BankDomain = field(default_factory=BankDomain)
    global_ctx: BaseGlobalContext = field(default_factory=BaseGlobalContext)
```

### 2. Define the Process (The Logic)
```python
from theus.contracts import process

@process(
    # STRICT CONTRACT
    inputs=['domain_ctx.accounts'],
    outputs=['domain_ctx.accounts', 'domain_ctx.total_reserves', 'domain_ctx.sig_fraud_detected'],
    errors=['ValueError']
)
def transfer(ctx, from_user: str, to_user: str, amount: int):
    # 1. Input Validation
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    # 2. Business Logic (Operating on Shadow Copies)
    sender_bal = ctx.domain_ctx.accounts.get(from_user, 0)
    
    if sender_bal < amount:
        # Trigger Signal
        ctx.domain_ctx.sig_fraud_detected = True
        return "Failed: Insufficient Funds"

    # 3. Mutation (Optimistic Write)
    ctx.domain_ctx.accounts[from_user] -= amount
    ctx.domain_ctx.accounts[to_user] = ctx.domain_ctx.accounts.get(to_user, 0) + amount
    
    return "Success"
```

### 3. Run with Safety (The Engine)
```python
from theus.engine import TheusEngine

# Setup Data
sys_ctx = BankSystem()
sys_ctx.domain_ctx.accounts = {"Alice": 1000, "Bob": 0}

# Initialize Engine
engine = TheusEngine(sys_ctx, strict_mode=True)

# 🚀 PRO TIP: Auto-Discovery
# Instead of registering manually, you can scan an entire directory:
# engine.scan_and_register("src/processes")

engine.register_process("transfer", transfer)

# Execute
result = engine.run_process("transfer", from_user="Alice", to_user="Bob", amount=500)

print(f"Result: {result}")
print(f"Alice: {sys_ctx.domain_ctx.accounts['Alice']}") # 500
```

---

## 🛠️ CLI Tools

Theus provides a powerful CLI suite to accelerate development and maintain architectural integrity.

*   **`python -m theus.cli init <project_name>`**: Scaffolds a new project with the standard V2 structure (`src/`, `specs/`, `workflows/`).
*   **`python -m theus.cli audit gen-spec`**: Scans your `@process` functions and automatically populates `specs/audit_recipe.yaml` with rule skeletons.
*   **`python -m theus.cli audit inspect <process_name>`**: Inspects the effective audit rules, side effects, and error contracts for a specific process.
*   **`python -m theus.cli schema gen`**: Infers and generates `specs/context_schema.yaml` from your Python Dataclass definitions.

---

## 🧠 Advanced Architecture

### The Transaction Engine
Theus uses a **Hybrid Transaction Model**:
*   **Scalars:** Updated in-place with an Undo Log (for speed).
*   **Collections:** Updated via **Shadow Copy** (for safety).
If a process crashes or is blocked by Audit, Theus rolls back the entire state instantly.

### The Heavy Zone (Optimization)
For AI workloads (Images, Tensors) > 1MB, use `heavy_` variables.
*   **Behavior:** Writes bypass the Transaction Log (Zero-Copy).
*   **Trade-off:** Changes to Heavy data are **NOT** reverted on Rollback.

### 🚀 High Performance Training (New in v2.2)
For Pure Training Loops (Simulations/Games) where Transaction safety is overkill:
```python
engine = TheusEngine(sys_ctx, strict_mode=False)
```
*   **Effect:** Completely disables Rust Transaction Layer (Zero Overhead).
*   **Performance:** Native Python execution speed.
*   **Trade-off:** No Rollback protection.


### The Audit Recipe (`audit.yaml`)
Decouple your business rules from your code.

```yaml
process_recipes:
  transfer:
    inputs:
      - field: "amount"
        max: 10000        # Max transfer limit
        level: "B"        # Block transaction
    outputs:
      - field: "domain.total_reserves"
        min: 0            # Reserves must never be negative
        level: "S"        # Safety Interlock (Stop System)
```

### The Orchestrator (FSM)
Manage complex flows using `workflow.yaml`:
```yaml
states:
  IDLE:
    events:
      CMD_TX: "PROCESSING"
  PROCESSING:
    entry: "transfer"
    events:
      EVT_SUCCESS: "NOTIFY"
      EVT_FAIL: "IDLE"
```

---

## 📚 Documentation

*   **[POP Whitepaper v2.0](https://github.com/dohuyhoang93/theus/tree/main/Documents/POP_Whitepaper_v2.0.md):** The formal theoretical basis.
*   **[Theus Master Class](https://github.com/dohuyhoang93/theus/tree/main/Documents/tutorials/en/):** 15-Chapter Zero-to-Hero Tutorial.
*   **[AI Developer Guide](https://github.com/dohuyhoang93/theus/tree/main/Documents/AI_DEVELOPER_GUIDE.md):** Prompt context for LLMs.

---

## ⚖️ License

*   **Software:** [MIT License](https://opensource.org/licenses/MIT).
*   **Whitepaper:** [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**Maintained by:** [Hoàng Đỗ Huy](https://github.com/dohuyhoang93)