
# Theus v2.2.5 - "Rust Core Deep Fix"
**Release Date:** 2026-01-13
**Author:** Do Huy Hoang
**Focus:** Rust Core Optimization & Protocol Compliance

## 🚀 Overview
Theus v2.2.5 represents a major maturation of the framework's core. The `TrackedList` and `TrackedDict` structures, which were previously partially implemented in Python (v2.2.3) or as thin wrappers (v2.2.4 "patch"), have been **completely moved to the Rust Core Microkernel**. The Python layer now only provides type aliases.

This "Deep Fix" ensures:
1.  **Maximum Performance:** Operations like mutations and access are handled by native Rust code.
2.  **Full Protocol Compliance:** Historically missing methods (`pop`, `clear`, `sort`, `reverse`, `insert`) are now fully supported with correct transaction logging.
3.  **Strict Typing:** Rust enforces stricter type safety and memory management.

## ✨ New Features

### 1. Full Python Mapping & Sequence Protocol Support (Rust Native)
Previously, `TrackedList` and `TrackedDict` missed several standard Python methods or implemented them inefficiently. v2.2.5 implements these directly in Rust via PyO3:
*   **TrackedList:**
    *   `insert(index, value)`: Fully supported with negative index handling.
    *   `clear()`: Efficient native clear with single log entry.
    *   `sort(key=..., reverse=...)`: Delegates to Python sort but logs the operation transactionally.
    *   `reverse()`: In-place reverse with logging.
    *   `pop(index)`: Standard behavior with return value logging.
    *   `extend(iterable)`: Bulk logging supported.
*   **TrackedDict:**
    *   `pop(key, default)`: Full support.
    *   `popitem()`: Returns (key, value) tuple LIFO.
    *   `clear()`: Native clear.
    *   `setdefault(key, default)`: Atomically checks and sets.

### 2. Transaction API Stabilization
*   **Renamed Field:** Internal Rust field `log` renamed to `delta_log` to avoid collision with the `log()` method.
*   **Property Exposure:** `Transaction.delta_log` is now a read-only property exposed to Python, returning a list of `DeltaEntry` objects.
*   **DeltaEntry Introspection:** `DeltaEntry` logs are now proper Python objects (not tuples) with accessible attributes: `path`, `op`, `value`, `old_value`.

## 🛠 Fixes & Improvements
*   **[Core]** Removed 100% of Pure Python implementation code from `theus/structures.py`. It is now a pure alias file.
*   **[Core]** Fixed `maturin` build issues related to `PyList` type imports.
*   **[Quality]** Codebase passes `cargo clippy -- -D warnings` (Strict Mode).
*   **[Compat]** `isize` indices in Python are correctly mapped to Rust usages via dynamic dispatch where necessary.

## 📦 Migration Guide
*   **For Users:** No code changes required. `from theus import TrackedDict` works as before, but faster and safer.
*   **For Contributors:** Rust toolchain (`cargo`, `maturin`) is now REQUIRED to build the framework. Pure Python "dev mode" without compilation is no longer supported for Core Structures.

## 🧪 Verification
*   **Unit Tests:** `./tests/test_structures_compliance.py` verified against the installed Rust extension.
