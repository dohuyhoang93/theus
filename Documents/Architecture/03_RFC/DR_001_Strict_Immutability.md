# Design Request: Enforcing Strict Immutability (Removal of TrackedList)

**Status:** PROPOSED
**Version:** V3.0-DR-001
**Related Documents:** tutorials/en/Chapter_02, Chapter_05, Chapter_07

## 1. Problem Statement
Theus V3 philosophy emphasizes **"Immutable Snapshot Isolation"** and the **"Return Pattern"** (Copy-on-Write).
However, the current Rust Core implementation (`theus_framework/src`) still supports Legacy Mutation via `TrackedList` and `TrackedDict`.

### Discovery
-   **File:** `src/guards.rs`
-   **Behavior:** When a Process declares `outputs=['ctx.items']`:
    -   Engine allows: `ctx.items.append(x)` (In-place mutation via `TrackedList`).
    -   Docs claim: This raises `AttributeError` (Immutability).
-   **Conflict:** There is a discrepancy between the **Aspirational V3 Documentation** (which teaches the ideal pattern) and the **Legacy Codebase Reality**.

## 2. Proposed Refactoring
To align the Codebase with V3 Architecture standards, we propose the following changes:

### 2.1. Refactor `guards.rs`
Modify `ContextGuard` to **ALWAYS** return `FrozenList` / `FrozenDict`, regardless of write permissions.

```rust
// Current (guards.rs)
if can_write {
    return TrackedList::new(...); // Allows .append()
}

// Proposed (V3 Strict)
// Always return Frozen. Forces user to use Copy-on-Write pattern.
let frozen = FrozenList::new(shadow_list);
return frozen;
```

### 2.2. Delete `tracked.rs`
Once `guards.rs` no longer uses `TrackedList`, the entire `src/tracked.rs` module becomes dead code and should be removed to reduce binary size and complexity.

### 2.3. Move `FrozenList`
Migrate the `FrozenList` struct from `tracked.rs` (which will be deleted) to `structures.rs` (core types).

## 3. Impact Analysis

| Component | Impact | Risk |
|:---|:---|:---|
| **Python Processes** | **Legacy Code Breakage**. Any process using `ctx.items.append()` will now raise `AttributeError`. | High (Requires Audit of User Code). |
| **Rust Core** | Simplified. Less state tracking logic complexity. | Low. |
| **Performance** | **Neutral/Slight Cost**. Copy-on-Write requires full list copy (`list(ctx.items)`) vs `TrackedList` which tracks deltas. | Optimization needed for massive lists? |

## 4. Recommendation
Approve this refactor only after alerting all developers to migrate their Process Code to the **Return Pattern**.

```python
# MIGRATION GUIDE
# OLD (Will Break)
ctx.items.append(x)

# NEW (Required)
new_items = list(ctx.items)
new_items.append(x)
return new_items
```
