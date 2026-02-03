# Chapter 25: The Outbox Pattern

In a Process-Oriented system, you must never perform external side-effects (DB writes, HTTP calls, Emails) directly inside a `@process`. If the transaction fails and rolls back, your side-effect cannot be undone.

The **Outbox Pattern** is the standard solution for this problem.

## 1. The Strategy

1.  **Process**: Instead of sending an email, your process writes a "command" to a list in the context (the `outbox_queue`).
2.  **Commit**: The Engine commits the data and the command atomically.
3.  **Relay**: A background worker (the Relay) polls the queue, executes the command, and then clears the queue.

## 2. Implementation Example

### Step 1: The Context
Add an `outbox_queue` to your domain.

```python
class MyDomain(BaseDomainContext):
    outbox_queue: list = []
```

### Step 2: The Process
Queue a message instead of acting.

```python
@process(inputs=['domain.outbox_queue'], outputs=['domain.outbox_queue'])
def place_order(ctx):
    # Atomic: Save order AND queue email notification
    msg = {"topic": "SEND_EMAIL", "to": "user@example.com", "body": "Order Confirmed"}
    
    new_queue = list(ctx.domain.outbox_queue)
    new_queue.append(msg)
    
    return new_queue
```

### Step 3: The Relay Worker
A separate async loop that monitors the state.

```python
async def relay_worker(engine):
    while True:
        queue = engine.state.domain.outbox_queue
        if not queue:
            await asyncio.sleep(0.5)
            continue
            
        for msg in queue:
            if msg['topic'] == "SEND_EMAIL":
                # Actually send the email here
                await send_real_email(msg['to'], msg['body'])
        
        # Clear the queue via an Engine process to ensure safety
        await engine.execute("clear_outbox_queue")
```

## 3. Benefits

- **Consistency**: If the `place_order` process fails, no email is ever "sent" to the queue.
- **Resilience**: If the Relay worker crashes, the messages remain in the `outbox_queue` and will be processed when it restarts.
- **Traceability**: All outgoing actions are recorded in the Theus Audit Log before they happen.
