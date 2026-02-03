---
id: INC-004
title: Output Path Resolution Overwrite
area: core
severity: medium
introduced_in: v3.1.0
fixed_in: v3.0.22
status: resolved
---

# INC-004: Output Path Resolution Overwrite

## Summary
When using `@process(outputs=['domain.order.orders'])` to update a nested list, the system incorrectly identified the parent object (`domain.order`) as the target to update. Since the process only returned the list, the entire parent object was overwritten by that list, causing data structure corruption.

## Root Cause
- **Granularity Mismatch:** The state update logic relied on matching the longest existing path. Since `orders` might initially be empty or strictly typed, the resolver fell back to the parent `order` object.
- **Mental Model:** Design assumed "Output = Object to Replace", failing to account for "Output = Specific Field of an Object".

## Resolution
- **Granular Setters:** Implemented `deep_update_at_path` which supports dot-notation expansion.
- **Verification:** `tests/02_safety/repro_path_resolution.py`.
