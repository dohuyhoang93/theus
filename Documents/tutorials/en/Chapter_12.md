# Chapter 12: Zone Architecture - Clean Architecture v2

This chapter summarizes Zone knowledge to help you build Scalable Systems.

## 1. The Holy Trinity

| Zone | Prefix | Definition | Survival Rules |
| :--- | :--- | :--- | :--- |
| **DATA** | (None) | **Single Source of Truth.** Business Assets. | Always Replayed. Must be protected by strict Audit. |
| **SIGNAL** | `sig_` | **Control Flow.** Events, Commands, Flags. | Never use as Input for Data Process. Self-destruct after use. |
| **META** | `meta_` | **Observability.** Logs, Traces, Debug info. | No effect on Business Logic. Usually Read-only or Write-once. |

## 2. Boundary Rules
Engine v2 enforces strict boundary rules:

- **Rule 1: Data Isolation.** Process calculating Data should only depend on Data. Its output should also be Data.
- **Rule 2: Signal Trigger.** Signal should only appear at Output of a Process to notify Orchestrator.
- **Rule 3: Meta Transparency.** Meta can be written anywhere (for timing), but never used in `if/else` business logic.

## 3. Why drop old `CONTROL` zone?
In v1, we had `CONTROL`. But practically it overlapped with Global Config and Signal.
In v2:
- Static Config -> **Global Context**.
- Dynamic Signals -> **Signal Zone**.
Everything is now clearer and Orthogonal.

---
**Exercise:**
Review your code. Any variables named wrongly? E.g., `ctx.domain.is_finished` (currently Data) -> should it be `ctx.domain.sig_finished` (Signal)?
