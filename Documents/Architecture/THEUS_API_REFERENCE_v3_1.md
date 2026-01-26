# Theus Framework v3.1 - API Reference

This document provides a comprehensive reference for the public APIs of the Theus Framework v3.1.
**Updated: January 2026**

---

## 🏗️ Core API (`theus`)

The top-level package exports the essential tools for building applications.

```python
from theus import TheusEngine, process, ContractViolationError
```

### 🧠 Mental Model: Which API to use?

To avoid confusion between Legacy and New APIs, follow this simple rule:

| Role | Primary Interface | Behavior | Recommended For |
| :--- | :--- | :--- | :--- |
| **App Developer** | `ctx` (inside `@process`) | **Implicit & Safe**. Mutations are auto-tracked by the Engine. | 99% of Business Logic. |
| **System Integrator** | `engine.state` | **Read-Only / Debug**. Use for monitoring or manual scripts. | Debugging, Shell, Orchestration. |
| **Core Hacker** | `engine.transaction()` | **Explicit**. Manual commit control. | Framework extensions, complex atomic batches. |

> **Implication:** As a developer writing processes, you generally **ignore** `state.domain` vs `state.domain_proxy`. You just interact with `ctx`.

---

### 1. Decorator: `@process`
Used to define a Theus Process. Transforms a standard function into a managed unit of work.

```python
@process(
    inputs: List[str] = [], 
    outputs: List[str] = [], 
    semantic: SemanticType = SemanticType.EFFECT, 
    errors: List[str] = [], 
    side_effects: List[str] = [], 
    parallel: bool = False
)
def my_function(ctx, *args, **kwargs): ...
```

*   **inputs**: List of context paths this process reads from (e.g., `['domain.order']`). Enforced as Read-Only.
*   **outputs**: List of context paths this process writes to. Enforced as Write-Only.
*   **semantic**: `SemanticType.PURE`, `EFFECT`, or `GUIDE`.
*   **parallel**: If `True`, runs in a separate process via `ProcessPool` (requires input args to be picklable).

---

## ⚙️ Engine API (`theus.engine`)

### Class `TheusEngine`
The central nervous system of Theus. Manages state, transactions, and execution.

#### Constructor
```python
engine = TheusEngine(
    context: Optional[BaseSystemContext] = None, 
    strict_mode: bool = True,
    strict_cas: bool = False,
    audit_recipe: Optional[AuditRecipe] = None
)
```
*   **strict_mode**: If `True`, enables `ContextGuard` and Linter checks.
*   **strict_cas** (New v3.1):
    *   `False` (Default): Smart CAS. Allows updates even if versions differ, provided the specific *target keys* have not been modified.
    *   `True`: Strict CAS. Rejects any update if the global state version has changed (Optimistic Locking).
*   **audit_recipe**: Configuration for the Audit System.

#### Methods

*   **`register(func)`**:
    Registers a `@process` function with the engine. Validates architectural constraints.

*   **`execute(func_or_name, *args, **kwargs) -> Any`**:
    Executes a process transactionally. Supports async/await.
    *   **Features:** Atomic Commit, Automatic Backoff (via ConflictManager), VIP Locking.

*   **`execute_workflow(yaml_path: str)`**:
    Runs an orchestration workflow defined in Flux DSL YAML.

*   **`scan_and_register(path: str)`**:
    Auto-discovery. Scans directory for `@process` functions and registers them.

*   **`transaction()`**:
    Returns a manual `Transaction` object (Rust Core) for batch updates.

---

## 💾 State & Memory API

Access via `engine.state`.

### Class `State` (Rust Core)
*   **`version`** (int): Current global state version.
*   **`domain`** (property): **Legacy**. Returns a `FrozenDict` (Immutable Copy).
    *   *Warning:* Has higher read throughput but unsafe for nested mutation checks.
*   **`domain_proxy(read_only=False)`** (method): **New v3.1**. Returns a `SupervisorProxy`.
    *   **Supervisor Model:** Wraps the live object reference.
    *   **Safe:** Enforces Deep Immutability and Transaction Isolation.
    *   **Usage:** `proxy = state.domain_proxy(); val = proxy.nested.key`

### Heavy Assets (`engine.heavy`)
Managed Shared Memory allocation for Zero-Copy tensor sharing.

*   **`alloc(key, shape, dtype)`**: Allocate a segment.
*   **`ctx.heavy['key']`**: Zero-copy Numpy view access within a process.

---

## 🛡️ Context API (`theus.context`)

Base classes for application structure.

*   **`BaseSystemContext`**: Root container.
*   **`BaseDomainContext`**: Domain data container.
*   **`BaseGlobalContext`**: Global config container.

### ContextGuard (Runtime Protection)
When running a `@process`, `ctx` is wrapped in a `ContextGuard`.
*   **v3.1 Update:** `ContextGuard` now uses `SupervisorProxy` for nested dictionaries. This ensures that even deep accesses like `ctx.domain.nested.field` are tracked and isolated within the transaction.

---

## 🔨 CLI Tools (`theus.cli`)

Usage: `python -m theus.cli <command> <subcommand>`

| Command | Subcommand | Arguments | Description |
| :--- | :--- | :--- | :--- |
| **init** | | `name`, `--quiet` | Initialize new project (Universal Scaffold). |
| **check** | | `path`, `--format` | **New v3.1**. Run POP Static Analysis (Linter). |
| **audit** | `gen-spec` | | Generate `audit_recipe.yaml` from code. |
| **audit** | `inspect` | `process_name` | View effective rules for a process. |
| **schema** | `gen` | `--context-file` | Generate YAML Schema from Python dataclasses. |

---
*Generated for Theus v3.1*
