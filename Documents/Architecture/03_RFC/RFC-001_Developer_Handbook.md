---
id: RFC-001-HANDBOOK
title: Semantic Policy Developer Handbook
author: Antigravity (AI Architect)
status: guide
---

# 📘 Theus Developer Handbook: Semantic Policy Implementation

This handbook is the definitive guide for developers building systems with **Theus Semantic Policy Architecture (RFC-001)**. It covers context planning, coding patterns, and advanced conflict resolution.

---

## 🏗️ Phase 1: Context Planning (Namespace Architecture)

Modern Theus applications use a **Modular Namespace Architecture** to organize data and policies.

### 1.1 The Strategy Context (Immutable & Private Focus)
`src/context/strategy.py`

```python
from theus.context import BaseDomainContext
from dataclasses import field

class StrategyContext(BaseDomainContext):
    # [Policy: IMMUTABLE]
    # 'meta_' prefix ensures strategies cannot mutate params at runtime.
    # INHERITANCE: Logic flows down to nested children.
    meta_params: dict = field(default_factory=lambda: {
        "risk_limit": 0.02,
        "symbols": ["BTC/USD", "ETH/USD"],
        "hyper_parameters": {"alpha": 0.5, "beta": 0.9}
    })

    # [Policy: PRIVATE]
    # 'internal_' prefix hides this from all View/Observer processes.
    internal_calculations: dict = field(default_factory=dict)
```

### 1.2 The Portfolio Context (Audit & Mutation Focus)
`src/context/portfolio.py`

```python
from theus.context import BaseDomainContext
from dataclasses import field

class PortfolioContext(BaseDomainContext):
    # [Policy: APPEND_ONLY]
    # 'log_' ensures we can add fills but NEVER delete history.
    log_executions: list = field(default_factory=list)

    # [Policy: MUTABLE]
    # Standard field for high-frequency updates.
    current_positions: dict = field(default_factory=dict)
```

### 1.3 The Main System Assembly
`src/context/system.py`

```python
from theus.context import BaseSystemContext, Namespace
from .strategy import StrategyContext
from .portfolio import PortfolioContext

class AlgoTradingContext(BaseSystemContext):
    # Wiring Namespaces
    strategy = Namespace(StrategyContext)
    portfolio = Namespace(PortfolioContext)

    # Global Shared Memory (Heavy Zone)
    # [Policy: HEAVY] Ref-Swap only.
    heavy_order_book: object = None 
```

---

## 🚀 Phase 2: Execution Patterns (The 4 Complexity Cases)

### 🟢 Case 1: Standard Transaction (The Happy Path)
**Goal:** Record a trade execution while updating positions.

```python
@process(
    inputs=["strategy.meta_params"], 
    outputs=["portfolio.log_executions", "portfolio.current_positions"]
)
def execute_trade(ctx, symbol: str, quantity: float):
    # 1. READ CONFIG (Immutable) - Zero Copy
    risk_limit = ctx.strategy.meta_params["risk_limit"]
    
    # 2. UPDATE STATE (Mutable) - Shadow Copy
    old_qty = ctx.portfolio.current_positions.get(symbol, 0.0)
    ctx.portfolio.current_positions[symbol] = old_qty + quantity
    
    # 3. AUDIT LOG (AppendOnly) - Restricted Proxy
    ctx.portfolio.log_executions.append({
        "symbol": symbol, "qty": quantity, "risk": risk_limit
    })
```

### 🔵 Case 2: Deep Verification (The Nested Reader)
**Goal:** Verify a nested configuration parameter.

```python
# No outputs declared -> Pure View Mode
@process(inputs=["strategy.meta_params"])
def analyze_strategy_drift(ctx):
    # ATTEMPT 1: Nested Mutation -> BLOCKED
    # ctx.strategy.meta_params["hyper_parameters"]["alpha"] = 0.6
    # Raise: PermissionError("Recursive Immutability violation")
    
    return ctx.strategy.meta_params["risk_limit"]
```

### 🟠 Case 3: High Contention (The Edge Case)
**Goal:** 1000 processes reading Shared Memory concurrently.

```python
# 'parallel=True' + 'heavy_' prefix = Maximum Performance
@process(inputs=["heavy_order_book", "portfolio.current_positions"], parallel=True)
def validate_mark_to_market(ctx):
    # HEAVY ZONE ACCESS: Zero-Copy, Direct Pointer
    # Safe because it is physically isolated from Transaction Log.
    market_price = ctx.heavy_order_book.get_mid_price("BTC/USD")
    
    pos = ctx.portfolio.current_positions.get("BTC/USD", 0)
    return pos * market_price
```

### 🔴 Case 4: Emergency Override (The Conflict Case)
**Goal:** Delete a corrupt log entry from an `AppendOnly` list.

```python
from theus.contracts import AdminTransaction, SemanticType

# 'GUIDE' semantic hints this is manual intervention
@process(outputs=["portfolio.log_executions"], semantic=SemanticType.GUIDE)
def emergency_rollback_log(ctx, log_id: str):
    # STANDARD MODE:
    # ctx.portfolio.log_executions.pop() -> FAIL (AppendOnly)
    
    # ADMIN MODE: Break Glass
    with AdminTransaction(ctx, reason="INC-019 Fix Duplicate"):
        logs = ctx.portfolio.log_executions
        for i, entry in enumerate(logs):
            if entry["id"] == log_id:
                logs.pop(i) # ALLOWED via Overlay
                break
```

---

## 🛡️ Troubleshooting Guide

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `PermissionError: DELETE capability denied` | Attempted `.pop()` on an `AppendOnly` list (`log_`). | Use `AdminTransaction` or redesign data structure. |
| `PermissionError: Mutation denied on Immutable` | Attempted write on `meta_` config. | Check if logical error, or use `AdminTransaction` for config reload. |
| `ContractViolation: Modified but not in outputs` | Mutated variable not declared in `@process`. | Add path to `outputs=[...]`. |
| `AttributeError: 'NoneType'` | Accessed `internal_` private field. | Check process privileges. |

---

## 🎓 Design Principles
1.  **Prefix is Law:** `meta_`, `log_`, `internal_`, `heavy_`. 
2.  **Inheritance is Deep:** Immutability flows down to all children.
3.  **Process is King:** Only `@process` can elevate permissions.
4.  **Admin is Explicit:** Breaking rules requires a paper trail.
