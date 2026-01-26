# 🤖 Theus Framework v3.0: AI Coding Standards & Agent Guidelines

**Target Audience:** AI Assistants (GPT-4, Claude, Gemini, Copilot) & Autonomous Agents.
**Purpose:** Rapid understanding of Rust-First Architectural Invariants, Strict Mode Constraints, and Flux DSL patterns in Theus v3.0.

---

## 1. Core Philosophy: The Microkernel OS
Theus is NOT a library; it is a **Process-Oriented Operating System (Rust Microkernel)**.
Your code (`@process`) does not own data. It requests temporary, guarded access to a global **Context**.

### The 3+1 Axis Context Model
Every data point is defined by 3 axes. You MUST respect them:
1.  **Layer (Scope):** `Global` (Config/Env) / `Domain` (Session/User) / `Local` (Ephemeral).
2.  **Semantic (Role):** `Input` (Read-only) / `Output` (Read-Write).
3.  **Zone (Policy):**
    *   **DATA:** Normal Business State. Transactional (Undo/Redo).
    *   **META (`meta_`):** Observability/Metrics. Log-only.
    *   **HEAVY (`heavy_`):** High-Perf Tensors/Blobs. Bypasses Transaction Log (No Undo).

    > **NOTE on SIGNALS:** Signals (`sig_` events) are no longer stored in variables. They are ephemeral messages handled by the **Flux DSL**. Do not add `sig_` fields to your Domain Class.

**CRITICAL INVARIANT:** Never mutate Context directly. Always use the injected `ctx` (ContextGuard).

---

## 2. Strict Mode (Default: ON)
Theus v3.0 enforces `strict_mode=True`. Violating these rules causes `ContractViolationError` or `PermissionError`.

### Rule 1: Explicit Contracts
Every process MUST be decorated with `@process` and declare exact `inputs/outputs`.

> **⚠️ v3.0 BREAKING CHANGE:** Contract paths use `domain_ctx.*` not `domain.*`.

```python
# ✅ CORRECT (v3.0)
@process(inputs=['domain_ctx.user_id'], outputs=['domain_ctx.profile'])
def fetch_profile(ctx): ...

# ❌ WRONG (PermissionError)
def fetch_profile(ctx): ... 
```

### Rule 2: Immutable Inputs
Attributes declared in `inputs` are **Read-Only**.
```python
# ❌ WRONG (PermissionError: Illegal Write)
ctx.domain_ctx.user_id = "new_id" 
```

### Rule 3: No Signal Inputs
You CANNOT declare `inputs=['domain_ctx.sig_start']`. Signals are processed by **Flux DSL**, not passed as data to processes.

### Rule 4: No Private Access
Accessing `ctx._internal` or `ctx.target._data` is BLOCKED.

---

## 3. API Changes (v3.0)

| v2.2 | v3.0 | Notes |
|:-----|:-----|:------|
| `engine.register_process(name, func)` | `engine.register(func)` | Name auto-detected |
| `engine.run_process(name, **kwargs)` | `engine.execute(func_or_name, **kwargs)` | Accepts func or string |
| `domain.*` paths | `domain_ctx.*` paths | Required change |

---

## 4. Optimization: The HEAVY Zone
For AI workloads (Images, Tensors, Embeddings), use the `HEAVY` zone to avoid RAM explosion.

**Mechanism:**
-   Prefix variable with `heavy_` (e.g., `heavy_frame`, `heavy_weights`).
-   Theus **Process** writes directly to memory (Zero-Copy).
-   **No Undo:** If transaction fails, `heavy_` variables are NOT reverted (Dirty Write).
-   **Use Case:** Only for data > 1MB where eventual consistency > atomicity.

```python
@process(inputs=[], outputs=['domain_ctx.heavy_frame'])
def capture_camera(ctx):
    # Fast write via Return (Engine maps output to Shared Memory)
    frame = np.zeros((1080, 1920, 3)) 
    return frame 
```

---

## 5. Orchestration: Flux DSL (v3.0)

> **⚠️ DEPRECATED:** FSM (states/events) is deprecated. Use Flux DSL.

Logic flow is defined in **YAML**, not Python. Theus Engine uses a Rust-based Flux DSL parser.

**Use Flux DSL keywords:**
```yaml
steps:
  - process: "initialize"
  
  - flux: if
    condition: "domain['is_valid'] == True"
    then:
      - "process_data"
    else:
      - "handle_error"
  
  - flux: while
    condition: "domain['count'] < 10"
    do:
      - "increment_count"
```

**Execute:**
```python
engine.execute_workflow("workflows/main.yaml")
```

---

## 6. Coding Patterns for AI Agents

### A. Implementing a Feature
1.  **Schema First:** Check `specs/context_schema.yaml`. Add fields if needed.
2.  **Define Process:** Create `src/processes/my_feature.py`.
3.  **Decorate:** Apply `@process` with `domain_ctx.*` paths.
4.  **Register:** Use `engine.register(func)` or `engine.scan_and_register("src/processes")`.
5.  **YAML:** Add steps to `workflows/main.yaml` using Flux DSL.

### B. Handling Structures (Lists/Dicts)
Theus returns `TrackedList` or `FrozenList`.
*   **DO NOT** do `if type(x) == list`. Use `isinstance(x, list)`.
*   **DO NOT** assign context lists to global variables (Zombie References).

---

## 7. CLI Cheatsheet (New in v3.0.2)
Use these tools to ensure compliance:

```bash
# 1. Lint your project for Theus Best Practices
python -m theus.cli check .

# 2. Create a new project scaffold
python -m theus.cli init my_new_agent

# 3. Audit contract violations
python -m theus.cli audit src/processes
```

---

## 8. Quick Reference

```python
# Standard imports
from theus import TheusEngine, process
from theus.structures import StateUpdate
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

# Process decorator (v3.0)
@process(
    inputs=['domain_ctx.items', 'global_ctx.max_limit'],
    outputs=['domain_ctx.items', 'domain_ctx.counter'],
    errors=['ValueError']
)
def my_process(ctx, arg1: str):
    # Logic...
    new_count = ctx.domain_ctx.counter + 1
    
    # Return Explicit Update (Recommended)
    return StateUpdate(domain={'counter': new_count})

# Engine setup (v3.0)
engine = TheusEngine(sys_ctx, strict_mode=True)
engine.register(my_process)
result = engine.execute(my_process, arg1="value") # Returns StateUpdate
```

---

## 8. Navigation (Project Structure)
*   **`src/`**: Rust Core (Do not touch unless modifying Kernel).
*   **`theus/`**: Python Wrapper & CLI.
*   **`specs/`**: The "Source of Truth" for Logic (YAMLs).
*   **`workflows/`**: Flux DSL workflow definitions.
*   **`pyproject.toml`**: Build config (Maturin).

---
*Generated for Theus Framework v3.0.2*