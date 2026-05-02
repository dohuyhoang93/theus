# Theus — Agent Instructions

Theus (v3.0.x) is a **Rust-powered Process-Oriented Programming (POP) framework** for building safe, transactional, auditable Python systems. It uses [PyO3/maturin](https://maturin.rs/) to bind a Rust microkernel to a Python API.

## Build & Test Commands

```bash
# Build (editable, auto-recompile Rust)
maturin develop --release

# Full CI pipeline: build → stubs → clippy → cargo test → pytest → integration
python scripts/Local_CI.py full

# Verify API parity (Rust ↔ Python alignment)
python scripts/Local_CI.py verify

# Individual steps
cargo test                           # Rust unit tests
cargo clippy -- -D warnings         # Rust linting (must pass)
pytest tests/                        # Python test suite (asyncio_mode="strict")
python tests/verify_api_parity.py   # Rust-Python API drift check

# After changing Rust exports, regenerate type stubs
python scripts/gen_stubs.py
```

**Environment setup for Python 3.14+:**
```bash
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
export PYO3_PYTHON=$(which python)
```

## Architecture

```
theus/          ← Python API layer (engine, contracts, context, audit, workflow, CLI)
src/            ← Rust microkernel (engine, FSM, zones, signals, shared memory, audit)
```

Data crosses the PyO3 FFI boundary as JSON/serde structures. Complex logic stays in Rust for performance; Python provides ergonomic wrappers.

See [Documents/00_Start_Here_Map.md](Documents/00_Start_Here_Map.md) for the documentation index, and [Documents/THEUS_DEVELOPMENT_WORKFLOW.md](Documents/THEUS_DEVELOPMENT_WORKFLOW.md) for the full dev/release workflow.

### Key Source Files

| File | Role |
|------|------|
| `src/engine.rs` | Core transaction engine, `TheusEngine`, `Transaction` |
| `src/zones.rs` | Zone Physics — prefix-based field semantics |
| `src/audit.rs` | Ring-buffer audit system |
| `src/fsm.rs` | Workflow / finite-state-machine engine |
| `src/signals.rs` | `SignalHub`, `SignalReceiver` (v3.1+) |
| `src/shm_registry.rs` | Managed shared memory registry (v3.2+) |
| `theus/contracts.py` | `@process` decorator — declares inputs/outputs/errors |
| `theus/context.py` | Context hierarchy (`BaseSystemContext`, `BaseDomainContext`, `NamespaceRegistry`) |
| `theus/engine.py` | Python `TheusEngine` wrapper |

## Core Conventions

### Zone Prefixes (field naming is semantic)

```python
data_*    # Persistent, auditable, transactional (default)
sig_*     # Signal: transient, ephemeral, not replayed
cmd_*     # Command variant of signal
meta_*    # Diagnostic metadata — read-only for business logic
heavy_*   # Large objects (tensors, blobs) — log-only, no copy
log_*     # Append-only journal entries
```

### Process Contract Pattern

```python
from theus import process, StateUpdate

@process(
    inputs=['domain.accounts'],   # fields the process may read
    outputs=['domain.accounts'],  # fields the process may write
    errors=['ValueError'],        # expected exceptions
    semantic='effect',            # pure | effect | guide
    parallel=False
)
def transfer(ctx, from_user: str, to_user: str, amount: int):
    accounts = dict(ctx.domain.accounts)   # copy the FrozenDict to mutate
    if accounts.get(from_user, 0) < amount:
        raise ValueError("Insufficient funds")
    accounts[from_user] -= amount
    accounts[to_user] = accounts.get(to_user, 0) + amount
    return StateUpdate(domain={'accounts': accounts})
```

## Common Pitfalls

1. **`SupervisorProxy` ≠ `dict`** — `isinstance(ctx.domain, dict)` is `False`. Use `dict(ctx.domain)` or `ctx.domain.to_dict()` to unwrap.
2. **Writes are not visible inside the same transaction** until commit. Processes see a snapshot.
3. **Don't store runtime objects** (asyncio tasks, file handles, DB connections) in `State`. Store only IDs/strings; keep live objects in a module-level ephemeral registry.
4. **Zone prefix determines behavior** — a field named `heavy_model` is automatically treated as a large object. Naming is not cosmetic.
5. **Rust-Python API drift** — when updating a Rust export, always update the Python wrapper and run `python scripts/Local_CI.py verify`.

## Tests

```
tests/01_core/      — engine, contracts, context
tests/02_safety/    — immutability, guards
tests/03_audit/     — audit system
tests/06_flux/      — workflow FSM
tests/09_v3_2/      — sub-interpreter / shared memory
tests/10_integration/
```

Mark slow tests with `@pytest.mark.slow`; they are excluded by default (`-m "not slow"`).

## Documentation

- Architecture & specs: [Documents/Architecture/](Documents/Architecture/)
- Known technical debt: [Documents/Technical-Debt-v3.0.23.md](Documents/Technical-Debt-v3.0.23.md)
- POP philosophy: [Documents/POP_Manifesto.md](Documents/POP_Manifesto.md)
- API reference: [Documents/Architecture/01_Specs/](Documents/Architecture/01_Specs/)
