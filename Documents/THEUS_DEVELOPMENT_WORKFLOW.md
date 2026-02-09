# Theus Development Workflow & Defense Protocol

This document outlines the strict workflow required for contributing to Theus Framework, ensuring synchronization between the **Rust Core** (High Performance) and **Python Wrappers** (Developer Experience).

---

## 🏗️ Phase 1: Local Development (The Inner Loop)

When modifying the Rust Core (e.g., adding a parameter or feature), follow this sequence:

### 1. Modify Rust Core
Edit `src/*.rs` files. Add your new logic or parameters (e.g., adding `timeout` to a method).

### 2. Build & Sync (Automated)
Instead of just running `maturin develop`, run the unified cross-platform script:
```bash
python scripts/dev.py build
```
**What this does:**
1.  Compiles Rust extension (`maturin develop`).
2.  **DEFENSE LAYER 1:** Automatically runs `scripts/gen_stubs.py`.

### 3. Update Python Wrapper
Open `theus/engine.py` (or relevant file).
*   Your IDE/Linter will now warn you if you call the Rust function incorrectly.
*   Update the Python method signature to match the Rust Core.

### 4. Verify Parity (Self-Check)
Run the Parity Enforcer locally:
```bash
python scripts/dev.py verify
```
**DEFENSE LAYER 2:** Strictly compares Python Wrapper signatures vs Rust Core.
*   (Or run both build & verify with `python scripts/dev.py all`)

---

## 🚀 Phase 2: CI/CD Pipeline (The Outer Loop)

When you push code to GitHub (`git push`), the CI pipeline (`.github/workflows/CI.yml`) enforces "Zero Trust":

### Check 1: Drift Detection (Anti-Lazy Guard)
The CI runs `scripts/gen_stubs.py` and then `git diff --exit-code`.
*   **Scenario:** You changed Rust code but forgot to commit the updated `.pyi` file.
*   **Result:** **CI FAILS**. You must run build locally and commit the stub file.

### Check 2: API Parity (Anti-Desync Guard)
The CI runs `tests/verify_api_parity.py`.
*   **Scenario:** You updated Rust & Stubs, but forgot to update `theus/engine.py` wrapper.
*   **Result:** **CI FAILS**. It yells strict mismatches (e.g., "Missing argument `timeout` in wrapper").

### Check 3: Functional Tests
Standard `pytest` suite runs to verify logic.

---

## 📦 Phase 3: Release

Only when all 3 Checks pass, the code is considered "Safe" to merge/release.
This guarantees that **Theus Python SDK never drifts from Theus Rust Microkernel**.
