# Release Notes v2.1.4 - The Flux Engine Upgrade

**Date:** 2025-12-30
**Codename:** Flux

## 🚀 Major Features

### 1. Flux Engine (Declarative Orchestration)
Theus v2.1.4 introduces **"Flux"**, a powerful control flow mechanism embedded directly into the YAML workflow engine. You no longer need to write boilerplate Python "Orchestrator Processes" for loops and conditionals.

- **`flux: while`**: Create loops directly in YAML. Safely guarded by `THEUS_MAX_LOOPS`.
- **`flux: if`**: Conditional branching based on Context state.
- **`flux: run`**: Group steps into logical blocks (inline sub-workflows).

**Example:**
```yaml
- flux: while
  condition: "domain.experiment.current_episode < 1000"
  do:
    - process: run_episode
    - flux: if
      condition: "domain.metrics.success_rate > 0.9"
      then:
        - process: save_checkpoint
```

### 2. Recursive Execution Model
The Engine core has been rewritten to support recursive step execution, enabling nested workflows and complex orchestration patterns while maintaining the strict safety guarantees of the Microkernel (Transaction/Shadowing).

### 3. ContextGuard Hierarchy Fix
- **[Fixed]** `ContractViolationError` when writing to child attributes of declared outputs (e.g., writing `domain.agent.state` when `domain.agent` is declared). The Guard now correctly supports hierarchical write permissions.

## 🛠 Improvements
- **Auto-Discovery**: Enhanced `scan_and_register` robustness in identifying valid `@process` decorators.
- **Docs**: Comprehensive updates to Architecture Spec (Chapter 7 & 12) reflecting the new Flux patterns.

## 📦 Migration Guide
- Existing linear workflows (`list` of strings) are still 100% supported.
- To use Flux features, switch your step definition to a list of dictionaries (Process/Flux objects).
