# Release Notes - Theus v2.2.6

**Date**: 2026-01-14
**Codename**: "Rustclad Core"
**Focus**: Performance, Safety, and Transactional Integrity

## 🚀 Major Highlights

### 1. Rust Core Optimization (TheusTensorGuard)
We have successfully migrated the core guarding and state management logic to Rust (`theus_core`), implementing a **3-Tier Optimization Strategy**:
*   **Tier 1 (Core Structures)**: `TrackedList` and `TrackedDict` moved to Rust for transactional integrity.
*   **Tier 2 (Tensors)**: **New `TheusTensorGuard`** (Rust, Zero-Copy) provides high-performance arithmetic operations for Numpy/Torch tensors, bypassing the Shadow Copy overhead for "Heavy" assets.
*   **Tier 3 (Generic)**: Hybrid `ContextGuard` (Rust + Python Wrapper) ensures backward compatibility while enforcing strict Zone permissions.

**Impact**:
*   **Performance**: Significant throughput improvement for guard-heavy workflows (approx 3x speedup).
*   **Safety**: Explicit "Heavy Zone" detection (`heavy_` prefix) prevents accidental deep copies of large tensors.
*   **Subclassing**: `ContextGuard` now properly supports Python subclassing via `#[pyclass(subclass)]`.

### 2. Quality Assurance
*   **Linting**: Passed `cargo clippy -D warnings` and `ruff check`.
*   **Verification**: Validated via integration tests.

## 🛠 Fixes & Improvements

*   **[Core]** `ContextGuard`: Added missing Magic Methods (`__len__`, `__getitem__`, `__add__`, etc.) to act as a proper Transparent Proxy.
*   **[Core]** `engine.rs`: Fixed `ContextGuard` instantiation signature to include `path_prefix`.
*   **[Build]** `Cargo.toml`: Updated PyO3 dependencies to 0.23.3.
*   **[Docs]** Updated build instructions and walkthroughs.

## 📦 Upgrade Instructions

To upgrade to Theus v2.2.6 from source (cloned repository):

```bash
# Navigate to the repository root (default: 'theus')
cd theus
pip install -e .
```

## Known Issues
*   None.
