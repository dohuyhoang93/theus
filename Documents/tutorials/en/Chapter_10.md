# Chapter 10: Performance Optimization & Memory Management

Performance in Theus is a balance between **Safety (Transactional Integrity)** and **Speed (Raw Access)**. This chapter guides you through optimizing Theus for high-load scenarios like Deep Learning Training.

## 1. The HEAVY Zone & Tier 2 Guards
**Concept vs Implementation:**
*   **HEAVY (The Policy):** A zone rule that says "This data is too big to snapshot (Undo Log)."
*   **Tier 2 Guard (The Mechanism):** The Rust object (`TheusTensorGuard`) that Theus hands you when you access a `heavy_` variable. It acts as a safety valve, allowing high-speed mutation (Zero-Copy) while still enforcing contract rules.

**Example:**
```python
# HEAVY Zone declaration
heavy_frame: np.ndarray = field(...)
```

When you access `ctx.domain_ctx.heavy_frame`:
1.  **Tier 1 (Normal):** Would try to deep-copy the array (Too slow).
2.  **Tier 2 (Heavy):** Returns a **Wrapper** that points to the original memory. You can modify it (`+=`), but you cannot Undo it.

> **Analogy:** Normal variables are documents in a photocopier (Snapshot). Heavy variables are sculptures; you work on the original because you can't photocopy a sculpture.

## 2. Strict Mode: True vs False
This switch controls the **Transaction Engine**.

| Mode | Use Case | Behavior |
|:-----|:---------|:---------|
| `strict_mode=True` | Production, Testing | Full transactions, rollback, strict checks |
| `strict_mode=False` | Training loops | Disabled transactions, native Python speed |

## 3. The Comparison Matrix (v3.0 Reference)

This table clarifies exactly which defense layers are active in each mode.

| Defense Layer | **Strict Mode = True** (Default) | **Strict Mode = False** (Training) | **Heavy Zone** (Tier 2 Guard) |
| :--- | :--- | :--- | :--- |
| **1. Transaction (Rollback)** | ✅ **Enabled** | ❌ **Disabled** | ❌ **Disabled** (Direct Write) |
| **2. Audit Policy** | ✅ **Active** | ⚠️ **Optional** | ✅ **Active** (Checks final state) |
| **3. Input Gate (Zone Check)** | ✅ **Strict** (No Signal/Meta) | ⚠️ **Relaxed** (Allow All) | N/A |
| **4. Private Access (`_attr`)** | ✅ **Blocked** | ⚠️ **Allowed** | N/A |
| **5. Performance** | Standard | 🚀 **Native Speed** | 🚀 **Zero-Copy** |

### Key Takeaway:
*   Use **HEAVY Zone** when you need **Speed** for **Big Data** (>1MB).
*   Use **Strict Mode = False** when you need **Maximum Speed** for **Training Loops**.
*   In v3.0, `strict_mode=False` **actually bypasses the Rust Transaction Layer** for real performance gains.

## 4. SignalHub Performance (v3.0)

The new Tokio-powered SignalHub achieves:
- **Throughput:** 2.7+ million events/second
- **Latency:** Sub-microsecond

```python
from theus_core import SignalHub

hub = SignalHub(capacity=10000)
receiver = hub.subscribe()

# High-throughput event sending
for i in range(1000000):
    hub.send("tick", {"step": i})
```

## 5. Avoiding Memory Leaks
Even with optimizations, Python references can leak.
*   **Restart Strategy:** For long training (1M+ episodes), restart the worker process periodically to clear fragmented memory.
*   **Avoid "God Objects":** Don't put everything in one giant List/Dict. Use specific dataclasses.
*   **Heavy Zone for Tensors:** Use `heavy_` prefix to avoid transaction log overhead.
