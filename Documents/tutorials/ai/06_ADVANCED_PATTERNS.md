 # Module 06: Advanced Patterns

> **For AI Assistants:** This module covers v3.0 advanced features: SignalHub, Heavy Zone optimization, Pipeline Pattern, and GUI integration.

---

## 1. SignalHub (Tokio-Powered)

SignalHub is a high-throughput event system backed by Tokio broadcast channels.

### Performance

- **Throughput:** 2.7+ million events/second
- **Latency:** Sub-microsecond
- **Backpressure:** Automatic queue lagging detection

### Basic Usage

```python
from theus_core import SignalHub, SignalReceiver

# Create hub
hub = SignalHub(capacity=1000)

# Create receiver
receiver: SignalReceiver = hub.subscribe()

# Send signal
hub.send("event_name", {"data": "value"})

# Receive (blocking)
event = receiver.recv()

# Receive (non-blocking)
event = receiver.try_recv()  # Returns None if empty
```

### Async Usage

```python
import asyncio

async def listener(receiver):
    while True:
        event = await receiver.recv_async()
        print(f"Received: {event}")

async def main():
    hub = SignalHub()
    receiver = hub.subscribe()
    
    # Start listener
    asyncio.create_task(listener(receiver))
    
    # Send events
    hub.send("tick", {"time": 1})
    await asyncio.sleep(0.1)
```

### Multiple Receivers

```python
hub = SignalHub()

# Each subscriber gets ALL messages
receiver1 = hub.subscribe()
receiver2 = hub.subscribe()

hub.send("broadcast", {})

# Both receive the message
event1 = receiver1.recv()
event2 = receiver2.recv()
```

---

## 2. Heavy Zone Optimization

For AI workloads with large data (tensors, images, embeddings).

### When to Use Heavy Zone

| Use Case | Size | Zone |
|:---------|:-----|:-----|
| User preferences | < 1KB | DATA |
| API responses | < 100KB | DATA |
| ML embeddings | > 1MB | HEAVY |
| Video frames | > 10MB | HEAVY |
| Model weights | > 100MB | HEAVY |

### Heavy Zone Behavior

```python
@dataclass
class MLContext(BaseDomainContext):
    # HEAVY zone: Zero-copy, no transaction log
    heavy_embeddings: object = None
    heavy_model_cache: object = None
```

**Trade-offs:**
- ✅ Zero-copy write (no RAM duplication)
- ✅ No transaction overhead
- ❌ NO rollback on error (dirty write)
- ❌ NOT replayed in deterministic replay

### Process Pattern

```python
@process(
    inputs=['domain.query'],
    outputs=['domain.heavy_embeddings']
)
def compute_embeddings(ctx):
    query = ctx.domain.query
    
    # Heavy computation
    embeddings = model.encode(query)  # Large numpy array
    
    # Return directly (Engine writes directly to Shared Memory via outputs map)
    return embeddings
```

---

## 3. Pipeline Pattern

v3.0 prohibits nested engine calls (calling `execute_workflow` inside a process) due to deadlock risks.

### Problem: Nested Engine Calls

```python
# ❌ WRONG - Causes deadlock in Rust multi-threaded core
@process(outputs=['domain.result'])
def bad_process(ctx):
    # This will deadlock!
    engine.execute_workflow("sub_workflow.yaml")
```

### Solution: Pipeline Pattern

Complex inner loops should be composed as pure Python functions:

```python
# ✅ CORRECT - Pure Python Pipeline

def think_step(state):
    """Pure function, no engine calls."""
    return {"thought": f"Thinking about {state}"}

def act_step(thought):
    """Pure function, no engine calls."""
    return {"action": f"Acting on {thought}"}

@process(
    inputs=['domain.observation'],
    outputs=['domain.action', 'domain.thought']
)
def agent_deliberation(ctx):
    """
    Single atomic process that runs entire pipeline.
    Engine lock held once for entire duration.
    """
    obs = ctx.domain.observation
    
    # Pipeline of pure functions
    thought = think_step(obs)
    action = act_step(thought)
    
    # Return all outputs (Atomic Commit)
    return action, thought
```

### Benefits

| Approach | Overhead | Deadlock Risk |
|:---------|:---------|:--------------|
| Nested Engine | ~100x | HIGH |
| Pipeline Pattern | ~1x | NONE |

---

## 4. Sub-Interpreters (Python 3.14+)

v3.0 supports running processes in separate sub-interpreters for true parallelism.

### Concept

```
Main Interpreter (GUI Thread)
    |
    +-- Sub-Interpreter 1 (Agent A)
    |       └── Own GIL
    |
    +-- Sub-Interpreter 2 (Agent B)
    |       └── Own GIL
    |
    +-- Rust Context (Shared Memory)
            └── Thread-safe, no GIL needed
```

### Pattern

```python
try:
    from concurrent.interpreters import create_interp
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    
from theus import TheusEngine

def run_in_subinterp(context_handle):
    """Run agent in isolated sub-interpreter."""
    if not CORE_AVAILABLE:
        return  # Fallback for non-supporting envs
    
    # Context shared via Rust backbone
    engine = TheusEngine.from_handle(context_handle)
    engine.execute_workflow("agent_workflow.yaml")

# Main thread
context_handle = engine.get_context_handle()

# Spawn sub-interpreters
if CORE_AVAILABLE:
    interp1 = create_interp()
    interp1.run(run_in_subinterp, context_handle)
```

### Heavy Zone + Sub-Interpreters

Data in `heavy_` variables remains accessible across interpreters via Rust shared memory.

---

## 5. GUI Integration Pattern

Theus `execute_workflow` is blocking (Run-to-Completion). For GUI apps:

### ❌ Wrong: Block Main Thread

```python
# GUI freezes!
def on_button_click():
    engine.execute_workflow("long_task.yaml")
```

### ✅ Correct: Background Worker

```python
import threading
from queue import Queue

class TheusWorker:
    def __init__(self, engine):
        self.engine = engine
        self.task_queue = Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def _run(self):
        while True:
            workflow = self.task_queue.get()
            try:
                self.engine.execute_workflow(workflow)
            except Exception as e:
                print(f"Error: {e}")
    
    def submit(self, workflow):
        self.task_queue.put(workflow)

# Usage
worker = TheusWorker(engine)

def on_button_click():
    worker.submit("long_task.yaml")  # Non-blocking
```

### Progress Updates

GUI polls context for updates:

```python
def update_gui():
    # Read from thread-safe context
    progress = engine.state.data.get('progress', 0)
    status = engine.state.data.get('status', 'idle')
    
    # Update GUI
    progress_bar.set(progress)
    status_label.set(status)
    
    # Schedule next update
    root.after(100, update_gui)  # Poll every 100ms
```

---

## 6. Schema Enforcement (Type Shield)

Optional strict typing using Pydantic for context validation.

```python
from pydantic import BaseModel
from theus_core import SchemaViolationError

class UserSchema(BaseModel):
    name: str
    age: int
    email: str

# Engine validates writes against schema
engine.set_schema(UserSchema)

try:
    # Async execute need await
    import asyncio
    await engine.execute(process_that_writes_invalid_data)
except SchemaViolationError as e:
    print(f"Invalid data: {e}")
```

**Overhead:** ~8 microseconds per write

---

## 7. Compare-and-Swap (Optimistic Locking)

For concurrent updates without blocking:

```python
while True:
    # Read current version
    state = engine.state
    current_version = state.version
    current_value = state.data['counter']
    
    # Compute new value
    new_value = current_value + 1
    
    # Try to update
    try:
        engine.compare_and_swap(
            expected_version=current_version,
            data={'counter': new_value}
        )
        break  # Success
    except VersionMismatchError:
        continue  # Retry
```

---

## 8. Outbox Pattern (Side Effects)

For managing external side effects (emails, HTTP calls):

```python
from theus_core import OutboxMsg

@process(
    inputs=['domain.orders', 'domain.outbox_queue'], 
    outputs=['domain.orders', 'domain.outbox_queue']
)
def create_order(ctx, order_data):
    # 1. Read Immutable Snapshot
    current_orders = ctx.domain.orders
    current_queue = ctx.domain.outbox_queue or []
    
    # 2. Compute New State (Copy-on-Write)
    new_orders = list(current_orders)
    new_orders.append(order_data)
    
    new_queue = list(current_queue)
    msg = OutboxMsg(topic="email", payload=order_data)
    new_queue.append(msg)
    
    # 3. Return (Atomic Commit of Data + Event)
    return new_orders, new_queue

# --- System Relay ---
# Engine commits changes. Separate worker polls 'domain.outbox_queue' and clears it.
```

---

## 9. CLI Tools Reference

```bash
# Initialize new project
py -m theus.cli init my_project

# Generate audit recipe from @process decorators
py -m theus.cli audit gen-spec

# Inspect process audit rules
py -m theus.cli audit inspect process_name

# Generate context schema from dataclasses
py -m theus.cli schema gen

# Run POP linter
py -m theus.cli check
```

### Linter Rules

| Rule | Description |
|:-----|:------------|
| POP-E01 | No `print()` - Use `ctx.log` |
| POP-E02 | No `open()` - Use Outbox |
| POP-E03 | No `requests` - No direct HTTP |
| POP-E04 | No `global` - Strict Context |

---

## 10. AI Implementation Checklist (Advanced)

- [ ] Use SignalHub for high-throughput events
- [ ] Prefix large data (>1MB) with `heavy_`
- [ ] Use Pipeline Pattern instead of nested engine calls
- [ ] Run Theus in background worker for GUI apps
- [ ] Use Compare-and-Swap for optimistic concurrency
- [ ] Queue side effects via Outbox pattern
- [ ] Run `theus.cli check` to validate code

---

*End of Documentation*

---

## Quick Navigation

- [00_QUICK_REFERENCE.md](./00_QUICK_REFERENCE.md) - Cheat sheet
- [01_CORE_CONCEPTS.md](./01_CORE_CONCEPTS.md) - POP fundamentals
- [02_CONTRACTS_AND_PROCESSES.md](./02_CONTRACTS_AND_PROCESSES.md) - @process decorator
- [03_ENGINE_AND_TRANSACTIONS.md](./03_ENGINE_AND_TRANSACTIONS.md) - TheusEngine API
- [04_WORKFLOW_FLUX_DSL.md](./04_WORKFLOW_FLUX_DSL.md) - Workflow YAML
- [05_AUDIT_SYSTEM.md](./05_AUDIT_SYSTEM.md) - Audit rules

---

*Generated for Theus Framework v3.0.0 - AI Developer Documentation*
