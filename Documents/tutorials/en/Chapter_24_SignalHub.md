# Chapter 24: SignalHub & Real-time Events

For high-throughput, low-latency communication between components, Theus provides **SignalHub**. 

While the standard `signal` field in a Theus Context is designed for transactional state changes that drive workflows, **SignalHub** is a non-transactional, asynchronous broadcasting system backed by Tokio.

## 1. When to use SignalHub vs State Signals

| Feature | State Signals (`ctx.signal`) | SignalHub |
| :--- | :--- | :--- |
| **Consistency** | Transactional (part of state) | Fire-and-forget |
| **Throughput** | Moderate (Locked by Engine) | **Ultra-high** (GIL-free) |
| **Persistence** | Recorded in Audit Log | Volatile (In-memory only) |
| **Use Case**| Workflow branching, FSM states | Real-time dashboards, log streaming |

## 2. Basic Usage

```python
from theus import SignalHub

# 1. Initialize the Hub
hub = SignalHub()

# 2. Subscribe (returns a Receiver object)
rx = hub.subscribe()

# 3. Publish an event
# Note: Data must be picklable or shareable
hub.publish("sensor_update", {"value": 42.5})

# 4. Receive (Blocking)
event = rx.recv()
print(f"Topic: {event.topic}, Data: {event.data}")
```

## 3. Async Integration

SignalHub is optimized for `asyncio`.

```python
import asyncio

async def monitor_events(rx):
    while True:
        # Use the async receive method
        event = await rx.recv_async()
        print(f"Live Update: {event.topic} -> {event.data}")

# Start the listener in the background
asyncio.create_task(monitor_events(hub.subscribe()))
```

## 4. Best Practices

1.  **Avoid Bloat**: Don't use SignalHub for large data transfers; use the **Heavy Zone** for that. SignalHub is for "notifications".
2.  **Filter Early**: Receivers get ALL messages published to the hub. Implement filtering logic in your listener.
3.  **Backpressure**: If a receiver is too slow, it may miss messages (lagging). SignalHub is designed for speed over perfect reliability.
