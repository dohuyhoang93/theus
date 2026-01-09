# Theus Framework v2.2.2 Release Notes

## 🚀 Critical Fix: Zero-Leak Training Architecture

This release addresses a critical memory leak ("Container Leak") that affected long-running training sessions (Reinforcement Learning / Deep Learning). It introduces a fully optimized `strict_mode=False` behavior in the Rust Core.

### 🐛 Bug Fixes
*   **[Core] Conditional Transaction Initialization:** The Rust Engine no longer creates `Transaction` objects when `strict_mode=False`. Previously, these objects were created unconditionally, causing `DomainContext` snapshots (containing PyTorch Tensors) to be retained in the Audit History, leading to a leak of +1500 tensors/episode.
*   **[Core] Context Guard Bypass:** `ContextGuard` now detects `strict_mode=False` and immediately returns raw values (`val`), bypassing the Shadow Copy mechanism entirely (Zero Overhead).
*   **[Fix] Audit Interlock:** Resolved an issue where Audit Policy could hold references to "Heavy" objects even after transaction drop.
*   **[UX] Log Noise Reduction:** Downgraded "Unsafe Mutation" warnings to DEBUG level when strict_mode is disabled, preventing log file explosion during training.

### 📚 Documentation
*   **New "Performance Optimization" Guide (Chapter 10):** Detailed instructions on when to use `strict_mode` toggle vs "Heavy Zone".
*   **New "Architecture Masterclass" (Chapter 16):** A deep dive into Theus's "Safety vs Speed" philosophy, explaining the architectural decisions behind POP.
*   **Updated Chapter 6:** Clarified Atomic Rollback and Transaction Lifecycle.

### ⚙️ How to Upgrade

#### Option A: PyPI (Recommended)
```bash
pip install theus==2.2.2 --upgrade
```

#### Option B: From Source
```bash
# Inside theus_framework directory
pip install .
```

### 🛠️ Configuration Update
If you are running **AI Training** or **Long Simulations**, update your Engine initialization to disable the transaction layer:
```python
engine = TheusEngine(system_ctx, strict_mode=False) 
```

### ✅ Verification
*   **Cargo Clippy:** Passed Clean (`-D warnings`).
*   **Memory Profile:** Verified 0MB leak over 200+ episodes on GridWorld benchmark.
