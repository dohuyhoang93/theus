# DR-002: Smart Guards & True Immutability Strategy

## 1. Problem Statement
In Theus v3.0, to achieve maximum performance (Zero-Copy), the framework returns direct references to underlying Rust data structures (`PyList`, `PyDict`).
While fast, this creates significant safety risks:
1.  **Unsafe Mutation:** Users can accidentally mutate state in-place (`ctx.items.append()`), bypassing the Transaction Rollback mechanism. This leads to silent data corruption on crash.
2.  **Broken Contracts:** `strict_mode` currently fails to enforce read permissions on nested properties because the `ContextGuard` layer is bypassed by the direct access pattern.
3.  **Reliance on Discipline:** Safety currently relies entirely on developer discipline (Copy-on-Write), which is prone to human error.

## 2. Proposed Solution: The "Smart Proxy" (v3.1)

We propose introducing a lightweight Rust-based **Smart Proxy** that wraps all Collections returned from Context.

### 2.1. Read-Only Wrapper (Row)
Instead of returning a raw `PyList`, the Engine should return a `FrozenList` wrapper that:
- Implements `Sequence` protocol (len, getitem, iter) -> **Pass-through to raw list** (Zero Overhead).
- Implements Mutation methods (append, pop, setitem) -> **Raise TypeError** ("Immutable View").
- Why it works: It stops "Accidental writes" while keeping "Zero-Copy reads".

### 2.2. Copy-on-Write helper
The wrapper should expose a `.mutate()` method:
```python
# Old (Manual)
items = list(ctx.domain.items)
items.append(1)

# New (Explicit & Optimized)
items = ctx.domain.items.mutate() # Returns a new Mutable Tracked List
items.append(1)
```

## 3. Implementation Strategy

### Phase 1: The `Immutable<T>` Wrapper
Create a generic Rust struct `Immutable<T>` where T is `PyList` or `PyDict`.
- Override `__setitem__`, `__delitem__`, `append`, `extend`.
- Forward all Read methods to inner `T`.
- **Cost:** Tiny allocation for the wrapper struct. Still O(1) for data access.

### Phase 2: Recursive Guarding
When accessing `ctx.domain.nested`, the Proxy should return `Immutable<Child>` instead of raw `Child`.
This ensures safety travels down the tree.

## 4. Configuration
Introduce `TheusEngine(safety_level=...)`:
- **RAW (Current v3.0):** Fastest. Zero wrappers. Unsafe.
- **SMART (Proposed v3.1):** Wrappers on top-level. Blocks top-level mutation.
- **PARANOID:** Recursive wrappers. Checks every read against Contract. Slower usage.

## 5. Impact Analysis
- **Performance:** Small overhead for wrapping/unwrapped (approx 50ns per access). Negligible for Business Logic.
- **Safety:** Prevents 95% of accidental mutations.
- **Backward Comp:** Fully compatible (behaves like a List).

## 6. Status
- **Status:** PROPOSED
- **Target:** Theus v3.1
- **Driver:** System Safety Team
