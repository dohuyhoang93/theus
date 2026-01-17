# Chapter 12: Zone Architecture - Clean Architecture v3

This chapter summarizes Zone knowledge to help you build Scalable Systems.

## 1. The Four Zones

| Zone | Prefix | Definition | Survival Rules |
| :--- | :--- | :--- | :--- |
| **DATA** | (None) | **Single Source of Truth.** Business Assets. | Always Replayed. Must be protected by strict Audit. |
| **SIGNAL** | `sig_`, `cmd_` | **Control Flow.** Events, Commands, Flags. | Never use as Input for Data Process. Self-destruct after use. |
| **META** | `meta_` | **Observability.** Logs, Traces, Debug info. | No effect on Business Logic. Usually Read-only or Write-once. |
| **HEAVY** | `heavy_` | **Large Data.** Tensors, Images, Blobs. | Zero-copy, no rollback. Use for data >1MB. |

## 2. Boundary Rules
Engine v3.0 enforces strict boundary rules:

- **Rule 1: Data Isolation.** Process calculating Data should only depend on Data. Its output should also be Data.
- **Rule 2: Signal Trigger.** Signal should only appear at Output of a Process to notify Workflow Engine.
- **Rule 3: Meta Transparency.** Meta can be written anywhere (for timing), but never used in `if/else` business logic.
- **Rule 4: Heavy Trade-off.** Heavy data bypasses transactions for speed, but has no rollback protection.

## 3. Zone Declaration Examples

```python
from dataclasses import dataclass, field
from theus.context import BaseDomainContext

@dataclass
class MyDomain(BaseDomainContext):
    # DATA - Normal business state
    balance: int = 0
    orders: list = field(default_factory=list)
    
    # SIGNAL - Control flow (sig_ or cmd_ prefix)
    sig_payment_complete: bool = False
    cmd_cancel_order: bool = False
    
    # META - Observability (meta_ prefix)
    meta_last_update: str = ""
    meta_process_count: int = 0
    
    # HEAVY - Large data (heavy_ prefix)
    heavy_model_weights: object = None
    heavy_image_buffer: object = None
```

## 4. Why We Removed `CONTROL` Zone
In v1, we had `CONTROL`. But practically it overlapped with Global Config and Signal.
In v3.0:
- Static Config -> **Global Context**.
- Dynamic Signals -> **Signal Zone**.
Everything is now clearer and Orthogonal.

---
**Exercise:**
Review your code. Any variables named wrongly? E.g., `ctx.domain_ctx.is_finished` (currently Data) -> should it be `ctx.domain_ctx.sig_finished` (Signal)?
