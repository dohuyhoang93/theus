---
id: INC-008
title: Async Deadlock in Workflow Execution
area: runtime
severity: medium
introduced_in: v3.0.0
fixed_in: v3.0.22
status: mitigated
---

# INC-008: Async Deadlock in Workflow Execution

## Summary
Executing blocking code (CPU-bound) directly within the `execute_workflow` async loop starved the event loop, causing keep-alive timeouts and deadlocks in the Orchestrator.

## Root Cause
- **Event Loop Blocking:** Python `asyncio` is cooperative. Long-running synchronous code stops the heart of the system.

## Resolution
- **Offloading:** `engine.py` logic now forces execution into `asyncio.to_thread` (Thread Pool) or `ProcessPool` (for Heavy tasks), ensuring the Event Loop remains responsive.
