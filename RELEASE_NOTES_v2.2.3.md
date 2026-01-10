# Theus Framework v2.2.3 Release Notes

## 🚀 Critical Stability Fix: Complete Memory Reference Cycle Resolution

This release definitively resolves the memory leak issues that have plagued `strict_mode=True` configurations. It introduces a forced cleanup mechanism in the Rust Core to break reference cycles between Transactions and Shadow Contexts.

### 🐛 Bug Fixes
*   **[Core] Transaction Reference Cleanup:** The `Transaction::commit` method in Rust now explicitly clears `shadow_cache` and `log` immediately after applying changes. This breaks the "Deadly Embrace" reference cycle between the Rust Transaction object and the Python Context object, allowing the Python Garbage Collector to reclaim memory immediately.
*   **[Core] Strict Mode Re-enabled:** `strict_mode=True` is now the recommended and stable configuration for all environments (Training & Production). The workaround of disabling strict mode to avoid leaks is no longer necessary.

### 🛡️ Security & Compliance
*   **Audit Trail Ready:** Verified full compatibility with comprehensive audit recipes (e.g., `multi_agent_audit.yaml`). The system can now enforce strict boundaries (min/max/interlock) without memory penalties.

### ⚙️ How to Upgrade

#### Option A: PyPI (If published)
```bash
pip install theus==2.2.3 --upgrade
```

#### Option B: From Source
```bash
# Inside theus_framework directory
maturin develop --release
# OR
pip install .
```

### 🛠️ Configuration Update
You should now **ENABLE** strict mode for maximum safety:
```python
engine = TheusEngine(
    system_ctx, 
    strict_mode=True,  # ✅ SAFE TO ENABLE
    audit_recipe=your_audit_recipe
) 
```

### ✅ Verification
*   **Leak Test:** Passed 200+ episodes of GridWorld training with stable memory usage (~318MB constant).
*   **Audit Test:** Confirmed correct trapping of outlier values without crashing the runtime.
