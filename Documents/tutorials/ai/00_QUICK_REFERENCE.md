# Theus Framework v3.0 - AI Quick Reference

> **Target:** AI Coding Assistants (Claude, GPT-4, Gemini, Copilot)  
> **Purpose:** Copy-paste patterns for Theus-based projects

---

## 🚀 Standard Imports

```python
from dataclasses import dataclass, field
from theus import TheusEngine, process, ContractViolationError
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext
from theus.structures import StateUpdate
```

---

## 📐 Context Definition Pattern

```python
@dataclass
class MyDomainContext(BaseDomainContext):
    # DATA ZONE (Persistent, Transactional)
    items: list = field(default_factory=list)
    counter: int = 0
    
    # SIGNAL ZONE 
    # NOTE: Do NOT define sig_ or cmd_ fields here. They are Dynamic.
    
    # HEAVY ZONE (Zero-Copy, No Rollback, prefix: heavy_)
    heavy_tensor: object = None

@dataclass
class MyGlobalContext(BaseGlobalContext):
    max_limit: int = 1000
    app_name: str = "MyApp"

@dataclass
class MySystemContext(BaseSystemContext):
    domain_ctx: MyDomainContext = field(default_factory=MyDomainContext)
    global_ctx: MyGlobalContext = field(default_factory=MyGlobalContext)
```

---

## 📝 Process Definition Pattern

```python
from theus.contracts import process, SemanticType

@process(
    inputs=['domain_ctx.items', 'global_ctx.max_limit'],
    outputs=['domain_ctx.items', 'domain_ctx.counter', 'domain_ctx.sig_alert'],
    errors=['ValueError'],
    semantic=SemanticType.EFFECT
)
def my_process(ctx, item_name: str, value: int):
    """Process docstring."""
    # 1. Validation
    if value < 0:
        raise ValueError("Value must be positive")
    
    # 2. Read inputs (immutable snapshot)
    max_limit = ctx.global_.max_limit
    current_items = ctx.domain.items
    current_counter = ctx.domain.counter
    
    # 3. Business logic (Compute New State)
    # Copy-on-Write is required for collections
    new_item = {"name": item_name, "value": value}
    
    new_items = list(current_items)
    new_items.append(new_item)
    
    new_counter = current_counter + 1
    
    # 4. Determine Signal
    alert = False
    if new_counter > max_limit:
        alert = True
    
    # 3. Return Logic using StateUpdate (Recommended)
    # Allows explicit signal firing
    
    signals = {}
    if new_counter > max_limit:
        signals['sig_alert'] = True
        
    return StateUpdate(
        data={
            'domain_ctx.items': new_items,
            'domain_ctx.counter': new_counter
        },
        signal=signals
    )
```

---

## ⚙️ Engine Initialization Pattern

```python
# 1. Create context
sys_ctx = MySystemContext()

# 2. Initialize engine
engine = TheusEngine(sys_ctx, strict_mode=True)

# 3. Register process (auto-discovers name from function)
engine.register(my_process)

# 4. Execute (Async)
import asyncio
result = await engine.execute(my_process, item_name="Test", value=100)
# OR by name:
result = await engine.execute("my_process", item_name="Test", value=100)
```

---

## 🔄 Workflow YAML (Flux DSL)

```yaml
# workflows/main_workflow.yaml
steps:
  # Simple process call
  - process: "validate_input"
  
  # Conditional branching
  - flux: if
    condition: "domain['is_valid'] == True"
    then:
      - "process_data"
      - "save_result"
    else:
      - "handle_error"
  
  # Loop
  - flux: while
    condition: "domain['items_left'] > 0"
    do:
      - "process_next_item"
  
  # Nested block
  - flux: run
    steps:
      - "cleanup"
      - "finalize"
```

### Execute Workflow

```python
engine.execute_workflow("workflows/main_workflow.yaml")
```

---

## ⚠️ Common Errors & Fixes

| Error | Cause | Fix |
|:------|:------|:----|
| `ContractViolationError` | Writing to undeclared output | Add path to `outputs=[]` |
| `PermissionError: Illegal Read` | Reading undeclared input | Add path to `inputs=[]` |
| `PermissionError: Illegal Write` | Writing to input-only path | Move path from `inputs` to `outputs` |
| `ContextLockedError` | Modifying ctx outside process | Use `with engine.edit()` |

---

## 🎯 Contract Path Rules

| Context | Path Format | Example |
|:--------|:------------|:--------|
| Domain | `domain.field` | `domain.items` |
| Global | `global.field` | `global.max_limit` |
| Nested | `domain.nested.field` | `domain.user.name` |

> **CRITICAL:** Use `ctx.domain` in Python code. In contracts, you can use `domain` or `domain_ctx` (legacy).

---

## 🏷️ Zone Prefixes

| Zone | Prefix | Behavior |
|:-----|:-------|:---------|
| DATA | (none) | Transactional, Rollback on error |
| SIGNAL | `sig_`, `cmd_` | Ephemeral (1-Tick), Managed by Rust |
| META | `meta_` | Observability only |
| HEAVY | `heavy_` | Zero-copy, NO rollback |

---

## 🛠️ CLI Cheatsheet

| Command | Description |
|:---|:---|
| `python -m theus.cli init my_proj` | Create new project |
| `python -m theus.cli check .` | Run Linter (Critical for AI) |
| `python -m theus.cli audit gen-spec` | Generate Audit Recipe |

---

## 🚫 Common Coding Pitfalls

### 1. Modifying Immutable Lists
```python
# ❌ WRONG
ctx.domain.items.append(x)  # AttributeError: 'FrozenList' is immutable

# ✅ CORRECT
new_items = list(ctx.domain.items)
new_items.append(x)
return {"domain.items": new_items}
```

### 2. Manual State Setup
Use `engine.edit()` context manager for test setup only.
```python
with engine.edit() as safe_ctx:
    safe_ctx.domain.counter = 100
```

---

## 🔍 Audit Levels

| Level | Exception | Action |
|:------|:----------|:-------|
| **S** (Safety) | `AuditStopError` | Emergency stop system |
| **A** (Abort) | `AuditAbortError` | Hard stop workflow |
| **B** (Block) | `AuditBlockError` | Rollback transaction only |
| **C** (Count) | None | Log warning only |

---

*Generated for Theus Framework v3.0.0 - AI Developer Documentation*
