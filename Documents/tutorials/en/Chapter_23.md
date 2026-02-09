# Chapter 23: SignalHub & Real-time Events

For high-throughput, low-latency communication between components, Theus provides **SignalHub**. 

While the standard `signal` field in a Theus Context is designed for transactional state changes that drive workflows, **SignalHub** is a non-transactional, asynchronous broadcasting system backed by Tokio.

---

## 1. When to use SignalHub vs State Signals

| Feature | State Signals (`ctx.signal`) | SignalHub |
| :--- | :--- | :--- |
| **Consistency** | Transactional (part of state) | Fire-and-forget |
| **Throughput** | Moderate (Locked by Engine) | **Ultra-high** (GIL-free) |
| **Persistence** | Recorded in Audit Log | Volatile (In-memory only) |
| **Use Case**| Workflow branching, FSM states | Real-time dashboards, log streaming |

---

## 2. Basic Usage

> **⚠️ Key Concept:** SignalHub transmits **plain string messages**, not structured objects.  
> To send structured data, serialize it first (e.g., JSON).

### Example: Simple Pub/Sub

```python
from theus import SignalHub

# 1. Initialize the Hub
hub = SignalHub()

# 2. Subscribe (returns a Receiver object)
rx = hub.subscribe()

# 3. Publish a message (plain string)
count = hub.publish("hello_world")
print(f"Message delivered to {count} subscribers")

# 4. Receive (Blocking)
msg = rx.recv()
print(f"Received: {msg}")  # Output: "Received: hello_world"
```

---

### Example: Structured Data

```python
import json
from theus import SignalHub

hub = SignalHub()
rx = hub.subscribe()

# Publish: Serialize to JSON string
data = {"sensor": "temperature", "value": 42.5, "unit": "°C"}
hub.publish(json.dumps(data))

# Receive: Deserialize from string
msg = rx.recv()
event = json.loads(msg)
print(f"Sensor: {event['sensor']}, Value: {event['value']}{event['unit']}")
# Output: Sensor: temperature, Value: 42.5°C
```

---

## 3. Async Integration

SignalHub provides **two methods** for async integration:

1. **`recv()`** - Blocking method (use with `asyncio.to_thread()`)
2. **`recv_async()`** - Native async method ⭐ **Recommended** (v3.0+)

### Comparison

| Feature | `recv()` + `to_thread()` | `recv_async()` (Native) |
|---------|-------------------------|------------------------|
| **Performance** | Slow (~2ms latency) | Fast (~160μs latency) |
| **Cancellation** | ❌ Cannot cancel | ✅ Can cancel |
| **Timeout** | ⚠️ Unreliable | ✅ Works with `wait_for()` |
| **Simplicity** | Requires wrapper | Direct await |

**Recommendation:** Use `recv_async()` for all async code (available since v3.0).

### Example: Async Listener (Legacy - using to_thread)

```python
import asyncio
import json
from theus import SignalHub

async def monitor_events(rx):
    """Background task to listen for events."""
    while True:
        # Wrap blocking recv() in thread pool
        msg = await asyncio.to_thread(rx.recv)
        event = json.loads(msg)
        print(f"[LIVE] {event['topic']}: {event['value']}")

# Setup
hub = SignalHub()
rx = hub.subscribe()

# Start listener task
asyncio.create_task(monitor_events(rx))

# Publish from main loop
for i in range(5):
    hub.publish(json.dumps({"topic": "counter", "value": i}))
    await asyncio.sleep(0.5)
```

---

### Example: Native Async (recv_async) ⭐ Recommended

```python
import asyncio
import json
from theus import SignalHub

async def monitor_events_async(rx):
    """Background task using native async."""
    while True:
        # Native async - clean and fast!
        msg = await rx.recv_async()
        event = json.loads(msg)
        print(f"[LIVE] {event['topic']}: {event['value']}")

# Setup
hub = SignalHub()
rx = hub.subscribe()

# Start listener task
asyncio.create_task(monitor_events_async(rx))

# Publish from main loop
for i in range(5):
    hub.publish(json.dumps({"topic": "counter", "value": i}))
    await asyncio.sleep(0.5)
```

**Output:**
```
[LIVE] counter: 0
[LIVE] counter: 1
[LIVE] counter: 2
[LIVE] counter: 3
[LIVE] counter: 4
```

---

## 4. Advanced: Timeout and Graceful Shutdown

### Timeout with recv_async()

```python
import asyncio
from theus import SignalHub

async def worker(rx):
    while True:
        try:
            # Wait max 5 seconds for message
            msg = await asyncio.wait_for(
                rx.recv_async(),
                timeout=5.0
            )
            process(msg)
        except asyncio.TimeoutError:
            print("No message in 5 seconds, still waiting...")
```

### Graceful Shutdown Pattern

```python
import asyncio
from theus import SignalHub

async def background_worker(rx, shutdown_event):
    """Worker that exits cleanly on shutdown."""
    while not shutdown_event.is_set():
        try:
            msg = await asyncio.wait_for(
                rx.recv_async(),
                timeout=0.5  # Check shutdown every 0.5s
            )
            process_message(msg)
        except asyncio.TimeoutError:
            continue  # No message, check shutdown

# Main application
hub = SignalHub()
rx = hub.subscribe()
shutdown = asyncio.Event()

worker_task = asyncio.create_task(
    background_worker(rx, shutdown)
)

# Later: initiate shutdown
shutdown.set()
await asyncio.wait_for(worker_task, timeout=2.0)
```

---

## 5. Error Handling: Lagged Receivers

If a receiver is too slow and the internal buffer (capacity: 100 messages) overflows, **it will raise a `RuntimeError`** on the next `recv()` call.

```python
hub = SignalHub()
rx = hub.subscribe()

# Flood the channel
for i in range(300):
    hub.publish(f"message_{i}")

# Receiver is lagged - will raise error
try:
    msg = rx.recv()
except RuntimeError as e:
    print(f"Channel lagged: {e}")
    # Output: Channel lagged: Channel Lagged: missed 200 messages
```

**Solutions:**

1. **Re-subscribe after lag** (Recommended for production):
   ```python
   async def resilient_listener(hub):
       rx = hub.subscribe()
       while True:
           try:
               msg = await rx.recv_async()
               process(msg)
           except RuntimeError as e:
               if "Lagged" in str(e):
                   # Re-subscribe to get fresh receiver
                   rx = hub.subscribe()
                   logger.warning(f"Channel lagged, re-subscribed: {e}")
                   continue
               raise
   ```

2. **Other strategies:**
   *   Increase processing speed in your listener.
   *   Filter messages early to reduce load.
   *   Accept message loss for non-critical events.

---

## 6. Best Practices

### 1. Keep Messages Small
SignalHub is for **notifications**, not bulk data transfer.

**❌ Bad:**
```python
# Sending 10MB numpy array as JSON (slow!)
hub.publish(json.dumps(large_array.tolist()))
```

**✅ Good:**
```python
# Send a reference to Heavy Zone
engine.heavy.alloc("embeddings", shape, dtype)
hub.publish(json.dumps({"type": "new_data", "key": "embeddings"}))
```

---

### 2. Filter Early in Listeners
Receivers get ALL messages. Implement filtering logic yourself.

```python
async def filtered_listener(rx, topic_filter):
    while True:
        msg = await rx.recv_async()  # ✅ Modern pattern
        event = json.loads(msg)
        
        # Filter by topic
        if event.get("topic") != topic_filter:
            continue
            
        print(f"Matched: {event}")
```

---

### 3. Accept Backpressure
SignalHub is designed for **speed over reliability**.
*   If your receiver is slow, it **will** miss messages.
*   This is intentional - use State Signals if you need guaranteed delivery.

---

## 7. Integration with Theus Engine

SignalHub works independently of the Theus Engine, but you can combine them:

```python
from theus import TheusEngine, SignalHub
from theus.contracts import process

hub = SignalHub()

@process(outputs=["domain.counter"])
def increment_and_notify(ctx):
    new_value = ctx.domain.counter + 1
    
    # Publish real-time notification
    hub.publish(json.dumps({
        "type": "counter_changed",
        "value": new_value
    }))
    
    return new_value
```

**Note:** SignalHub messages are **not transactional** and **not rolled back** if the process fails.  
For critical events, use the **Outbox Pattern** (Chapter 24).

---

## 8. API Summary

| Method | Signature | Description |
|--------|-----------|-------------|
| `SignalHub()` | Constructor | Create a new hub (no args) |
| `publish(msg: str)` | -> `int` | Broadcast message, returns subscriber count |
| `subscribe()` | -> `SignalReceiver` | Create new receiver |
| **`recv()`** | -> `str` | **Blocking** receive (use with `asyncio.to_thread()`) |
| **`recv_async()`** ⭐ | -> `Awaitable[str]` | **Native async** receive (v3.0+, cancellable, timeout support) |

---

## 9. Navigation

- [API Reference](./API_Reference.md)
- [Chapter 24: The Outbox Pattern](./Chapter_24_Outbox_Pattern.md)
- [Chapter 22: Inside Theus Engine - Transaction Mechanism](./Chapter_22.md)
