# Chapter 18: Transactional Outbox - Reliability Pattern

> **Target Audience:** Systems Architects needing "Exactly-Once" or "At-Least-Once" delivery guarantees.

The **Transactional Outbox** pattern is the gold standard for reliable distributed messaging. It ensures that a database transaction and an event publication happen **atomically** (either both succeed or both fail).

## 1. The Core Problem

Consider a standard API:
1. Update User Record (DB).
2. Send Email (SMTP).

**Failure Scenarios:**
- If DB fails, Email is not sent. (Good)
- If DB succeeds, but SMTP fails/crashes before sending. **(Data Inconsistency)**
- Result: User is updated, but no email sent (phantom state).

## 2. The Theus Solution: Built-in Outbox

Theus provides a native `Outbox` textbf{inside the Context Transaction}.

### Mechanism
1. **Prepare:** Instead of a side-effect, your process creates the message and adds it to a **State Queue** (e.g., `domain.outbox_queue`).
2. **Commit:** The process returns the new queue via `StateUpdate`. The Engine commits this atomically with the rest of the state using `compare_and_swap`.
3. **Relay:** A system-level worker pulls messages from `domain.outbox_queue` (Immutable Read), persists them, and then **Clears the Queue** via a new Transaction.

### Code Example

#### Step 1: User Process (Producer)
```python
from theus.contracts import process, OutboxMsg
# from theus.structures import StateUpdate (Implicit or Explicit return)

@process(
    inputs=['domain.outbox_queue', 'domain.user'], 
    outputs=['domain.outbox_queue']
)
def update_user_email(ctx):
    # 1. Read Inputs (Immutable)
    current_queue = ctx.domain.outbox_queue or []
    user = ctx.domain.user
    
    # 2. Logic: Create Message
    msg = OutboxMsg(topic="USER_UPDATED", payload={"id": user['id']})
    
    # 3. Create New State (Immutable Append)
    new_queue = list(current_queue)
    new_queue.append(msg)
    
    # 4. Return Data (Engine handles CAS)
    return new_queue
```

#### Step 2: System Relay (Consumer)
In your system loop (separate thread/process):

```python
# 1. Read Immutable State
state = engine.state
buffer = state.domain.get('outbox_queue', [])

if buffer:
    # 2. Persist (Side Effect)
    db.insert(buffer)
    
    # 3. Atomic Clear (CAS)
    # Reset queue to empty to acknowledge processing
    current_ver = state.version
    engine.compare_and_swap(current_ver, data={'domain': {'outbox_queue': []}})
```

## 3. Why This Pattern?

This follows the **Zero Trust** principle:
- **No Side Effects:** `ctx` is immutable. You cannot "send" from a process.
- **Atomicity:** The event exists IF AND ONLY IF the State exists.
- **Verification:** Unit tests just check the returned list. Zero mocking required.

---
**Summary:**
- Don't do I/O in your business logic.
- Put I/O intents in `ctx.outbox`.
- Let the System Relay handle the messy world of networks.
