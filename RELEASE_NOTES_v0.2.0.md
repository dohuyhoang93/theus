# Release Notes - Theus v0.2.0: The Industrial Awakening

**Release Date:** 2025-12-18
**Codename:** Solid Foundation

This major release transforms the experimental POP SDK into **Theus**, a production-ready "Operating System for Agents". It introduces core persistence, safety, and tooling features required for industrial deployment.

---

## 🌟 Highlights

### 1. Hybrid Context Zones (Context Drift Solution)
We solved the "God Object" anti-pattern by strictly segmenting the Context into 3 functional zones:

- **DATA Zone**: Persistent Business State. (Saved to DB/Snapshot).
- **SIGNAL Zone**: Transient Events/Commands. (Prefix `sig_`, `cmd_`). Automatically reset after tick.
- **META Zone**: Diagnostic & logging data. (Prefix `meta_`).

### 2. Semantic Process Contracts (The 4-Axes)
Decorators now enforce a complete semantic contract, not just I/O:

```python
@process(
    inputs=['domain.user'],
    outputs=['domain.status'],
    side_effects=['I/O', 'API'], # New
    errors=['ValueError']        # New
)
```

### 3. Industrial Tooling (CLI V2)
- **`theus init`**: Scaffolds a complete project with V2 best practices (Zone-aware Context, Semantic Decorators).
- **`theus schema gen`**: Automatically generates Data Schema from your Python Context, intelligently filtering out Signal/Meta fields.
- **`theus audit gen-spec`**: Parses your Python code to automatically generate/update `audit_recipe.yaml` with full semantic rules.

### 4. Unsafe Mode Verification
- Undecorated processes now trigger warnings and run in "Unsafe Mode" (bypassing Transaction/Rollback).
- Strict Mode (`THEUS_STRICT_MODE=1`) is fully enforced.

---

## 🛠 Breaking Changes

- **Renamed Package**: `pop` is now `theus`. Update your imports (`from pop import ...` -> `from theus import ...`).
- **Context Structure**: `SystemContext` now expects clear separation of layers (`global_ctx`, `domain_ctx`).
- **Config Files**: Moved from root `configs/` to `specs/` folder (`specs/context_schema.yaml`, `specs/audit_recipe.yaml`).

## 🐛 Bug Fixes

- Fixed `ContractViolationError` not being raised in specific loophole scenarios.
- Fixed `schema_gen` failing on `__init__` initialized Contexts.
- Fixed `audit_gen` ignoring `side_effects` and `errors`.
- Stabilized all 43 SDK regression tests.

---

## 🔮 What's Next? (Roadmap V2.2)

- **FSM-in-YAML**: Full State Machine definition inside `workflow.yaml`.
- **Async Scheduler**: `theus.scheduler` for non-linear execution.
- **Visualizer**: Web-based tool to view State Machine and Audit Logs.
