# Module 01: Core Concepts of Theus Framework

> **For AI Assistants:** This module explains the foundational architecture. Internalize these concepts before generating Theus code.

---

## 1. Philosophy: Process-Oriented Programming (POP)

Theus is NOT a library. It is a **Process-Oriented Operating System** for your code.

### Key Paradigm Shift

| Traditional | Theus POP |
|:------------|:----------|
| Objects own data + behavior | Context owns data, Process owns behavior |
| `obj.method()` mutates state | `process(ctx)` requests guarded access |
| Trust the code | Zero-Trust: verify every access |

### AI Implementation Rule

```
When generating Theus code:
1. NEVER put behavior in Context classes (no methods)
2. ALWAYS use @process decorator for logic
3. ALWAYS declare inputs/outputs explicitly
```

---

## 2. The 3-Axis Context Model

Every data point in Theus exists in a 3-dimensional space:

```
                         [Y] SEMANTIC
                    (Input vs Output)
                           ^
                           |
                   Input   |   Output
                  (Read)   |  (Write)
                           |
        +------------------+------------------+
       /|                 /|                  |
      / |       GLOBAL   / |                  |
     /  |               /  |   CONTEXT        |-----> [Z] ZONE
    +---+---+----------+   |   OBJECT         |   (Data/Signal/Meta/Heavy)
    |   |   |  DOMAIN  |   +------------------+
    |   +---+----------+--/
    |  /    |         |  /
    | /     |  LOCAL  | /
    +-------+---------+/
           /
          v
      [X] LAYER
   (Global/Domain/Local)
```

### Axis 1: Layer (Scope)

| Layer | Purpose | Lifespan | Example |
|:------|:--------|:---------|:--------|
| `global_ctx` | Configuration, Environment | Entire application | `max_workers`, `api_key` |
| `domain_ctx` | Business State, Session | Per-workflow/user | `user_profile`, `cart_items` |
| `domain_ctx` | Business State, Session | Per-workflow/user | `user_profile`, `cart_items` |
| `local` | **(Conceptual)** Process Scope | Internal function vars | Not an explicit Context object |

### Axis 2: Semantic (Permission)

| Semantic | Access | Contract Keyword |
|:---------|:-------|:-----------------|
| **Input** | Read-only | `inputs=[...]` |
| **Output** | Read-Write | `outputs=[...]` |

### Axis 3: Zone (Protection Policy)

| Zone | Prefix | Transaction | Replay | Use Case |
|:-----|:-------|:------------|:-------|:---------|
| **DATA** | (none) | ✅ Full | ✅ Yes | Business state |
| **SIGNAL** | `sig_`, `cmd_` | ❌ Transient | ❌ No | Events, control flow |
| **META** | `meta_` | ❌ Read-only | ❌ No | Logs, metrics |
| **HEAVY** | `heavy_` | ❌ Zero-copy | ❌ No | Tensors, images (>1MB) |

---

## 3. Context Design Pattern

### Standard Context Structure

```python
from dataclasses import dataclass, field
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class AgentDomainContext(BaseDomainContext):
    """
    Domain Context: Mutable business state.
    All fields are DATA zone by default.
    """
    # DATA ZONE - Persistent, Transactional
    memory: list = field(default_factory=list)
    current_goal: str = ""
    step_count: int = 0
    
    # HEAVY ZONE - Large data, bypasses transaction log
    heavy_embeddings: object = None
    heavy_embeddings: object = None
    heavy_image_buffer: object = None

@dataclass
class AgentGlobalContext(BaseGlobalContext):
    """
    Global Context: Immutable configuration.
    Treat as read-only during processes.
    """
    model_name: str = "gpt-4"
    max_steps: int = 100
    temperature: float = 0.7

@dataclass
class AgentSystemContext(BaseSystemContext):
    """
    System Context: Container for Domain and Global.
    This is passed to TheusEngine.
    """
    domain_ctx: AgentDomainContext = field(default_factory=AgentDomainContext)
    global_ctx: AgentGlobalContext = field(default_factory=AgentGlobalContext)
```

---

## 4. Zone Behavior Deep Dive

### DATA Zone (Default)

```python
# Normal fields without prefix -> DATA zone
items: list = field(default_factory=list)
counter: int = 0
```

**Behavior:**
- Full transaction support (commit/rollback)
- Replayed during deterministic replay
- Tracked by audit system
- **Immutability:** Collections (list/dict) are returned as `FrozenList`/`FrozenDict`. You MUST copy them before modification.

### SIGNAL Zone

**Concept:**
Signals are **Ephemeral Messages** (Events), not persistent state. They are managed by the Rust Engine (Tokio).

**Usage:**
- **Send:** Return `StateUpdate(signal={'cmd_stop': True})` from a process.
- **Receive:** Use `signal.get('cmd_stop')` in Flux Workflows.

**Prefixes:**
- `cmd_*`: Command directives (e.g., `cmd_stop`).
- `sig_*`: Notifications (e.g., `sig_user_joined`).

**Behavior:**
- **Ephemeral:** Exists for EXACTLY 1 Tick, then vanishes.
- **Dynamic:** Do NOT define them in `DomainContext` dataclass.
- **Control Flow:** Used to trigger Flux logic, not for data calculation.

**AI Rule:** Never try to read signals inside a Python `@process` (use Flux instead).

### HEAVY Zone

```python
# Prefix with heavy_
heavy_model_weights: object = None
heavy_video_frame: object = None
```

**Behavior:**
- Zero-copy write (no transaction overhead)
- NO rollback on error (dirty write)
- Use only for data >1MB where speed > atomicity

---

## 5. Lock Manager (Strict Mode)

When `strict_mode=True`, Context is LOCKED immediately.

### Illegal: Direct Mutation

```python
# ❌ WRONG - Raises ContextLockedError
sys_ctx.domain_ctx.counter = 10  # Outside @process
```

### Legal: Via Process

```python
# ✅ CORRECT - Return New State
@process(outputs=['domain.counter'])
def increment(ctx):
    return ctx.domain.counter + 1
```

### Legal: Via edit() (Setup/Testing Only)

```python
# ✅ CORRECT - Explicit unlock for setup
with engine.edit() as safe_ctx:
    safe_ctx.domain.counter = 0  # Initial setup
# Auto-relocked after with block
```

---

## 6. AI Implementation Checklist

When generating Theus Context code:

- [ ] Inherit from `BaseDomainContext` / `BaseGlobalContext` / `BaseSystemContext`
- [ ] Use `@dataclass` decorator
- [ ] Use `field(default_factory=...)` for mutable defaults (list, dict)
- [ ] Prefix signals with `sig_` or `cmd_`
- [ ] Prefix heavy data with `heavy_`
- [ ] NO methods in Context classes (behavior goes in processes)
- [ ] Define `domain_ctx` and `global_ctx` in SystemContext

---

*Next: [02_CONTRACTS_AND_PROCESSES.md](./02_CONTRACTS_AND_PROCESSES.md)*
