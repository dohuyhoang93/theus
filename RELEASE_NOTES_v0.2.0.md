# Theus v0.2.0 (Industrial Evolution)

## 🌟 Major Highlights
- **Microkernel Architecture**: Rebuilt purely on Clean Architecture (`IEngine`, `IScheduler`).
- **Orchestration**: FSM-based Workflow Management with Hybrid Linear Chains.
- **Concurrency**: `ThreadExecutor` enabling valid Non-blocking GUI integration.
- **Safety**: "Secure by Default" Context Guard, `LockManager`, and Safe External Mutation (`engine.edit`).
- **Governance**: Industrial Audit System (Input/Output Gates, S/A/B/C Levels).

### 3. Documentation Improvements
- **New Configuration Guide:** `Documents/GUIDES/configuration.md` details Workflow YAML and Audit syntax.
- **Architecture Spec:** Updated `Documents/SPECS/theus_v2_1_architecture.md`.
- **Showcase Skeleton:** `theus init` now generates a full feature demo including Security, Resilience, and Rollback tests.

### 4. Advanced Safety (Microkernel)
- **Transaction Rollback:** Automatic state reversion on process crash.
- **Context Guard:** Block-level permissions for data access.
- **Audit Interlock:** Runtime Schema validation.

## 🚀 Migration Guide (From v1)
1.  **Rename Imports:** `import pop` -> `import theus`.

## 📊 Feature Matrix & Verification Status

| Feature ID | Feature Name | Description | Status |
| :--- | :--- | :--- | :--- |
| **CORE-1** | **The Trinity** | Separation of Context (Data), Workflow (Logic), Config (Schema) | ✅ Verified |
| **ORCH-1** | **FSM Manager** | Event Driven State Machine | ✅ Verified (Demo System) |
| **ORCH-2** | **Signal Bus** | Async Event Loop integration | ✅ Verified |
| **CONC-1** | **Thread Pool** | Background Task Execution | ✅ Verified (Performance) |
| **PROT-1** | **Context Lock** | Thread-safe Mutex for Context | ✅ Verified (Safety Adv.) |
| **PROT-2** | **Strict Mode** | Blocking undeclared IO | ✅ Verified (Exploit Test) |
| **PROT-3** | **Transactions** | Auto-Rollback on Crash | ✅ Verified |
| **PROT-4** | **Safe Edit API** | `engine.edit()` for External Code | ✅ Verified |
| **AUDIT-1** | **IO Gates** | Pre/Post Execution Validation | ✅ Verified (Audit Test) |
| **CLI-1** | **Scaffolding** | `theus init` | ⚠️ Beta (Untested in Session) |
| **CLI-2** | **Auto-Gen** | `theus audit gen-spec` | ⚠️ Beta (Untested in Session) |

## 🚀 Readiness
The Runtime is considered **Production Ready**.
CLI Tooling is **Beta**.

## 📦 Installation
```bash
pip install theus
```
