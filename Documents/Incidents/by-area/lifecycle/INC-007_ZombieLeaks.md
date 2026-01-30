---
id: INC-007
title: Zombie Shared Memory Leaks
area: lifecycle
severity: medium
introduced_in: v3.0.0
fixed_in: v3.1.1
status: resolved
---

# INC-007: Zombie Shared Memory Leaks

## Summary
When Theus processes crashed (SIGKILL/Exception), the Managed Allocator (Heavy Zone) left orphaned Shared Memory segments (`/dev/shm/*`) and stale entries in the Registry. This eventually exhausted system memory.

## Root Cause
- **Lack of Cleanup:** No "Garbage Collection" for crashed processes. Python's `resource_tracker` is flaky with `multiprocessing`.
- **Registry Desync:** The JSONL registry file only appended, never pruned.

## Resolution
- **Startup GC:** `MemoryRegistry` now performs a scan at startup.
- **Liveness Check:** It checks if the PID owning a segment is still alive (using `sysinfo`). If dead, unlinks the SHM and rewrites the registry.
