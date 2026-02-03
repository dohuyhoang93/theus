---
id: INC-001
title: Silent Loss of Mutations in SupervisorProxy
area: core
severity: high
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-001: Silent Loss of Mutations in SupervisorProxy

## Summary
In-place mutations on Python collections (e.g., `list.append`, `set.add`, `dict.update`) accessed via `SupervisorProxy` were silently lost during transaction commits. Users received no error, but the data changes were not persisted, leading to latent data corruption.

## Background
Theus uses a `SupervisorProxy` to wrap Python objects accessed within a `Transaction`. This proxy intercepts attribute access and modifications to ensure changes are tracked and logged (`delta_log`). Transactions work by applying these deltas to the global state upon commit. The system relies on "Shadow Copies" (Copy-on-Write) to isolate transaction changes from the global state until commit.

## What Went Wrong
When a user accessed a mutable collection like `ctx.domain.items` (a list), `SupervisorProxy` returned a Shadow Copy of that list. If the user then called a built-in mutation method like `.append()`, the operation occurred directly on the Shadow Copy. Because `SupervisorProxy` only wraps the *access* (`__getattr__`) and not the *method call* itself (which happens in C), there was no interception hook. The `Transaction` remained unaware of the change (empty `delta_log`), and thus the mutated Shadow Copy was discarded at the end of the transaction.

## Impact
- **Affected:** All logic relying on in-place modification of lists, sets, or dictionaries within Theus Transactions.
- **Behavior:** Data loss. Features like "Add Tag", "Append Log", or "Update Metadata" silently failed.
- **Severity:** High. It violates the core database guarantee of Durability (D in ACID) without raising any exception.

## Root Cause
- **Design Limitation:** `SupervisorProxy` assumed that intercepting `__setattr__` and `__setitem__` was sufficient for tracking changes.
- **Invalid Assumption:** It did not account for "Internal Mutability" of Python built-ins which bypass Python-level attribute setters.
- **Missing Mechanism:** The `Transaction` commit logic relied solely on the explicit `delta_log` and ignored the state of the Shadow Copies it had created.

## Why This Was Hard to Detect
- **No Errors:** The code ran perfectly fine; the operation succeeded in memory (on the shadow), but wasn't committed.
- **Shadow Isolation:** Reads *within* the same transaction saw the change (because they read the same shadow), creating a false sense of correctness during debugging. The loss only happened *after* the transaction context exited.

## Resolution
We implemented **Differential Shadow Merging** in the Rust Core (`src/engine.rs`):
- **Tracking:** `Transaction` now maintains a `full_path_map` of all issued Shadow Copies.
- **Inference:** A new method `infer_shadow_deltas` is called at `__exit__`.
- **Deep Compare:** It iterates all tracked shadows, compares them deeply (RichCmp Eq) against their original versions.
- **Implicit Delta:** If a difference is found, a `SET` delta is automatically generated and added to the commit log.

## Long-Term Changes
- **In-Memory Truth Policy:** The system now recognizes the in-memory state of Shadow Copies as the "source of truth" at commit time, overriding explicit logs if conflicts arise.
- **Rust Core Audit:** Methods like `__exit__` in Rust Extensions must explicitly handle state synchronization.

## Preventive Actions
- **New Test Suite:** `tests/02_safety/test_silent_loss_comprehensive.py` covers Edge cases, Deep nesting, and Conflicts.
- **Documentation:** Added "Differential Shadow Merging" section to Architecture specs.

## Related
- **ADR:** Documents/Architecture/02_ADR/004_Analysis_Workflow_Complex.md (Related context)

## Lessons Learned
- **Trust but Verify Proxy:** Wrappers around C-Extension types are leaky. Always assume the underlying data can change backdoors.
- **Explicit vs Implicit:** If you can't force explicit APIs (like `set_items`), you must pay the cost of implicit discovery (Diffing).
