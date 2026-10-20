# Release Notes - Theus Framework v2.2.4

**Release Date:** 2026-01-11

## Summary
This is a patch release focused on improving the project skeleton (`theus init`) with better documentation and examples, plus minor code quality improvements.

---

## ✨ New Features

### Enhanced Project Skeleton
- **Flux Workflow Examples**: `TEMPLATE_WORKFLOW` now includes commented examples demonstrating advanced control flow: `flux: run`, `flux: if`, and `flux: while`.
- **Comprehensive Audit Recipe Template**: `TEMPLATE_AUDIT_RECIPE` now includes:
  - Full documentation of severity levels (S/A/B/C/I)
  - Documented dual threshold mechanism (`min_threshold`, `max_threshold`, `reset_on_success`)
  - List of all supported conditions: `min`, `max`, `eq`, `neq`, `min_len`, `max_len`
  - Five practical examples covering common use cases

### Auto-Discovery in Skeleton
- `main.py` template now uses `engine.scan_and_register()` for automatic process discovery instead of manual registration.

### Improved File Organization
- Workflow files are now placed in `workflows/` directory instead of `specs/` for better project structure.

---

## 🔧 Fixes & Improvements

### Code Quality
- Translated remaining Vietnamese docstrings to English in `contracts.py` and `engine.py` for consistency.
- Updated `@process` decorator examples to use `domain_ctx` instead of `domain` alias, ensuring compatibility with strict Rust Core type checking.

---

## 📦 Installation

```bash
pip install theus==2.2.4
```

Or build from source with Rust Core:
```bash
maturin develop --release
```

---

## 🔄 Upgrade Notes
No breaking changes. Existing projects do not need modification.

New projects created with `theus.cli init` will benefit from improved templates automatically.
