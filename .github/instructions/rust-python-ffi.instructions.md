---
description: "Use when editing Rust core files, Python wrappers, PyO3 exports, generated stubs, or API parity checks in Theus. Covers Rust-Python sync, stub regeneration, parity validation, and proxy-heavy FFI pitfalls."
name: "Theus Rust-Python FFI Sync"
applyTo:
  - "src/**/*.rs"
  - "theus/engine.py"
  - "theus/__init__.py"
  - "theus/theus_core.pyi"
  - "scripts/gen_stubs.py"
  - "tests/verify_api_parity.py"
---

# Theus Rust-Python FFI Sync

- Treat Rust exports, Python wrappers, and `theus/theus_core.pyi` as one interface surface
- After Rust signature or exported-type changes, run `python scripts/Local_CI.py verify`; use `python scripts/gen_stubs.py` for a fast local stub refresh
- If you are not using `Local_CI.py`, set `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` and `PYO3_PYTHON` for the active interpreter before building
- Keep wrapper signatures and names aligned with `tests/verify_api_parity.py`
- Generated stub changes are expected after export changes; do not forget to keep them in sync
- `SupervisorProxy` objects are not normal Python containers. Prefer `.to_dict()` or explicit copies before serialization, inspection, or mutation
- Heavy-zone objects and Rust-backed proxies are not safe payloads for process boundaries; pass metadata or shared-memory handles and reattach in the worker

See [Documents/tutorials/ai/09_FFI_AND_ARCHITECTURE_REFERENCE.md](Documents/tutorials/ai/09_FFI_AND_ARCHITECTURE_REFERENCE.md) for boundary-specific patterns and examples.