# Theus Agent Instructions

Theus is a Rust-plus-Python Process-Oriented Programming framework. The Rust core lives in `src/`; the Python API and wrappers live in `theus/`; generated stubs live in `theus/theus_core.pyi`.

## Use These Commands

- Preferred verification loop: `python scripts/Local_CI.py verify`
- Full local pipeline: `python scripts/Local_CI.py full`
- Build/install only: `python scripts/Local_CI.py build`
- Rust tests only: `cargo test`
- Rust lint only: `cargo clippy --all-targets --all-features -- -D warnings -W clippy::pedantic`
- Python tests only: `python -m pytest tests/`
- Manual integration suite: `python tests/manual/run_suite.py`
- Fast stub refresh after Rust export changes: `python scripts/gen_stubs.py`

If you run build commands manually instead of `Local_CI.py`, set `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` and `PYO3_PYTHON` to the active interpreter first. `Local_CI.py` already does this.

## Architecture Anchors

- `src/engine.rs`, `src/conflict.rs`, `src/zones.rs`, `src/guards.rs`: transaction engine, CAS/conflicts, zone behavior, safety guards
- `src/signals.rs`, `src/shm_registry.rs`, `src/shm.rs`, `src/fsm.rs`: signals, shared memory, workflow runtime
- `theus/engine.py`, `theus/contracts.py`, `theus/context.py`: Python wrapper layer, `@process` contracts, context types
- `tests/`: automated suite grouped by subsystem; `tests/manual/`: verification scripts excluded from pytest by default

## Conventions That Matter

- Zone prefixes are semantic, not cosmetic: `data_*`, `sig_*`, `cmd_*`, `meta_*`, `heavy_*`, `log_*`
- `ctx.domain` and nested values are usually `SupervisorProxy` wrappers, not plain `dict` or `list`; use `dict(...)`, `list(...)`, or `.to_dict()` before mutating or serializing
- Processes work on snapshot reads. Writes are not visible until commit
- Use copy-on-write for collections and return explicit updates via `StateUpdate`
- Do not store live runtime objects in state; store ids, names, or metadata and keep live handles in ephemeral registries
- Heavy-zone and proxy-backed objects are not generally pickle-safe; for worker processes, pass shared-memory metadata or handles, then reattach in the worker
- When changing Rust exports or Python wrappers, treat `src/`, `theus/`, and `theus/theus_core.pyi` as one contract and run `python scripts/Local_CI.py verify`

## Read Before Going Deep

- Documentation map: [Documents/00_Start_Here_Map.md](Documents/00_Start_Here_Map.md)
- AI quick reference: [Documents/tutorials/ai/00_QUICK_REFERENCE.md](Documents/tutorials/ai/00_QUICK_REFERENCE.md)
- Rust/Python boundary notes: [Documents/tutorials/ai/09_FFI_AND_ARCHITECTURE_REFERENCE.md](Documents/tutorials/ai/09_FFI_AND_ARCHITECTURE_REFERENCE.md)
- API reference: [Documents/Architecture/01_Specs/THEUS_API_REFERENCE.md](Documents/Architecture/01_Specs/THEUS_API_REFERENCE.md)
- Current technical debt: [Documents/Technical-Debt-v3.0.23.md](Documents/Technical-Debt-v3.0.23.md)
