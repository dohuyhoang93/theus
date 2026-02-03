---
id: INC-006
title: Unsafe FrozenDict allows Shallow Mutation
area: core
severity: high
introduced_in: v3.0.0
fixed_in: v3.0.22
status: resolved
---

# INC-006: Unsafe FrozenDict allows Shallow Mutation

## Summary
The legacy `FrozenDict` implementation protected top-level keys but allowed modification of nested mutable objects (e.g., `state.d['nested']['a'] = 1`), bypassing immutability guarantees.

## Root Cause
- **Shallow Freeze:** Python's `MappingProxyType` or custom `__setitem__` blocks only direct assignment. It does not recursively freeze children.

## Resolution
- **Supervisor Architecture:** Replaced `FrozenDict` with `SupervisorProxy(read_only=True)`. This proxy intercepts *all* recursive access and wraps children in Read-Only proxies on the fly.
