---
id: INC-003
title: Data Loss due to Shallow Merge in Transaction.update()
area: core
severity: high
introduced_in: v3.0.2
fixed_in: v3.0.22
status: resolved
---

# INC-003: Data Loss due to Shallow Merge in Transaction.update()

## Summary
Using `tx.update(data={"domain": ...})` caused sibling fields (e.g., `domain.payment`) to be silently deleted/overwritten. The system performed a key-level replacement instead of the expected recursive deep merge, leading to data corruption in nested structures.

## Background
Theus transactions allow users to patch the global state. Documentation implied a "Smart Merge" capability. Users expected `tx.update` to behave like a recursive patch (e.g., JSON Merge Patch), preserving parts of the tree not explicitly mentioned in the update payload.

## What Went Wrong
The `Transaction::update` implementation simply replaced the value at the top-level key provided. For an input like `{"domain": {"order": ...}}`, it replaced the entire `domain` object with the new dictionary, discarding any existing fields in `domain` (like `payment`) that were not present in the update.

## Impact
- **Affected:** Any process using partial updates on complex immutable state trees via `tx.update()`.
- **Behavior:** Silent deletion of sibling data.
- **Severity:** High. Data loss without error.

## Root Cause
- **Ambiguous Contract:** `update()` semantics were not strictly defined as "Merge" vs "Replace".
- **Implementation gap:** The recursive merge logic only existed in the specific `Conflict Resolution` module, not in the general `Transaction` API.

## Why This Was Hard to Detect
- **Partial usage:** Unit tests might have asserted `domain.order` was correct, missing checks for `domain.payment`.
- **Lazy Evaluation:** If sibling fields weren't accessed immediately, the data loss might manifest much later.

## Resolution
- **Granular Update Support:** Implemented "Output Path Resolution" and "Granular Setters" in v3.1.2.
- **Recursive Merge:** Updated `Transaction` logic to perform a recursive deep merge (or equivalent granular delta generation) for Dictionary inputs.
- **Verification:** Verified by `tests/02_safety/repro_overwrite.py`.

## Preventive Actions
- **API Clarification:** Updated docs to distinguish between `update` (Merge) and `set` (Replace).
- **Tooling:** Added `theus.utils.set_nested_value` helper to safely target leaf nodes without touching parents.

## Related
- **Original Report:** Documents/Incidents/reports/THEUS_FEEDBACK_OVERWRITE_ISSUE.md

## Lessons Learned
- **Semantics Matter:** "Update" is a dangerous word. It means "Merge" to some, "Replace" to others. Be explicit (e.g., `patch` vs `put`).
- **Data Safety:** Default behavior for dictionaries should favor safe merging or require explicit flags for destructive replacement.
