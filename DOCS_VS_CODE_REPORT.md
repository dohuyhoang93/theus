
# Theus Framework: Documentation vs Source Code Discrepancy Report

**Date:** 2026-01-17
**Version Reviewed:** v3.0.0 (Source)

## Executive Summary
A review of the `theus_framework` source code against the documentation in `Documents/tutorials/ai` reveals critical discrepancies that will prevent users from successfully running code copied from the documentation. The most significant issues are the incorrect Context API reference (`domain_ctx` vs `domain`) and the synchronous execution examples for an asynchronous API.

## 🚨 Critical Issues (Code Will Crash)

### 1. Context Access Mismatch (`domain_ctx` vs `domain`)
- **Documentation Claim**: `00_QUICK_REFERENCE.md` and `02_CONTRACTS_AND_PROCESSES.md` state that users **MUST** use `ctx.domain_ctx` to access domain state inside processes.
  > `> **CRITICAL:** Always use domain_ctx NOT domain. Rust Core enforces strict paths.`
- **Source Code Reality**: `theus/engine.py` defines `RestrictedStateProxy` (the object passed as `ctx` to processes) which exposes a `.domain` property but **NO** `.domain_ctx` property.
- **Impact**: Code following the documentation will raise `AttributeError: 'RestrictedStateProxy' object has no attribute 'domain_ctx'`.
- **Recommendation**:
  - **Option A (Code Fix)**: Add `@property def domain_ctx(self): return self.domain` to `RestrictedStateProxy` in `theus/engine.py`.
  - **Option B (Docs Fix)**: Update all docs to use `ctx.domain` instead of `ctx.domain_ctx`.

### 2. Execution Pattern Mismatch (Sync vs Async)
- **Documentation Claim**: `00_QUICK_REFERENCE.md` shows synchronous execution of processes:
  ```python
  result = engine.execute(my_process, ...)
  ```
- **Source Code Reality**: `TheusEngine.execute` in `theus/engine.py` is defined as `async def execute(...)`. It returns a coroutine that must be awaited.
- **Impact**: The documented code will return a coroutine object instead of the result, eventually raising `RuntimeWarning: coroutine was never awaited`.
- **Recommendation**: Update documentation to show `val = await engine.execute(...)` or `asyncio.run(engine.execute(...))`.

### 3. Sub-Interpreter Module Import Crash
- **Documentation Claim**: `06_ADVANCED_PATTERNS.md` mentions support for Python 3.14+ sub-interpreters.
- **Source Code Reality**: `theus/parallel.py` imports `concurrent.interpreters` at the top level.
- **Impact**: Importing `theus.parallel` on any standard Python version (< 3.12/3.13) will immediately raise `ImportError: No module named 'concurrent.interpreters'`, crashing the application.
- **Recommendation**: Wrap the import in a `try...except` block or move it inside the function/class that uses it.

## ⚠️ Semantic & Logic Discrepancies

### 4. Contract Output Permission Logic
- **Observation**: `theus/engine.py` > `_check_output_permission` contains logic to strip `data.` prefix (`check_key = key[5:]`).
- **Issue**: This assumes a specific mapping between Contract paths (e.g., `domain_ctx.x`) and Internal State keys (e.g., `data.domain.x`). If documentation insists on `domain_ctx`, but internal keys are `domain`, this normalization might be fragile or incorrect without explicit aliasing.

## ✅ Verified Correct Features
- **SignalHub**: Correctly implemented in `src/signals.rs` and exposed via `theus_core`.
- **Audit System**: `AuditLevel`, `RingBuffer`, and `AuditRecipe` implementations in `src/audit.rs` match documentation.
- **Flux DSL**: `src/fsm.rs` correctly implements the YAML workflow structure (`flux: if`, `while`, `run`).

## Proposed Action Plan
1.  **Immediate**: Fix `theus/engine.py` to add `domain_ctx` alias to `RestrictedStateProxy`.
2.  **Immediate**: Update `00_QUICK_REFERENCE.md` to reflect `async/await` requirement.
3.  **Refactor**: Guard `theus/parallel.py` imports.
