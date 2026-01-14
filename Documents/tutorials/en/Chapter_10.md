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

When you access `ctx.domain.heavy_frame`:
1.  **Tier 1 (Normal):** Would try to deep-copy the array (Too slow).
2.  **Tier 2 (Heavy):** Returns a **Wrapper** that points to the original memory. You can modify it (`+=`), but you cannot Undo it.

> **Analogy:** Normal variables are documents in a photocopier (Snapshot). Heavy variables are sculptures; you work on the original because you can't photocopy a sculpture.

## 2. Strict Mode: True vs False
This switch controls the **Transaction Engine**.

## 3. The Comparison Matrix (v2.2.6 Reference)

This table clarifies exactly which defense layers are active in each mode.

| Defense Layer | **Strict Mode = True** (Default) | **Strict Mode = False** (Dev/Flexible) | **Heavy Zone** (Tier 2 Guard) |
| :--- | :--- | :--- | :--- |
| **1. Transaction (Rollback)** | ✅ **Enabled** | ✅ **Enabled** | ❌ **Disabled** (Direct Write) |
| **2. Audit Policy** | ✅ **Active** | ✅ **Active** | ✅ **Active** (Checks final state) |
| **3. Input Gate (Zone Check)** | ✅ **Strict** (No Signal/Meta) | ⚠️ **Relaxed** (Allow All) | N/A |
| **4. Private Access (`_attr`)** | ✅ **Blocked** | ⚠️ **Allowed** | N/A |
| **5. Performance** | Standard | Standard (No speed gain) | 🚀 **Zero-Copy** |

### Key Takeaway:
*   Use **HEAVY Zone** when you need **Speed** (Big Data).
*   Use **Strict Mode = False** when you need **Flexibility** (Debugging/Listeners).
*   **NEVER** assume `strict_mode=False` makes code faster in v2.2.6. It only makes it "looser".

## 4. Avoiding Memory Leaks
Even with optimizations, Python references can leak.
*   **Restart Strategy:** For long training (1M+ episodes), restart the worker process periodically to clear fragmented memory.
*   **Avoid "God Objects":** Don't put everything in one giant List/Dict. Use specific dataclasses.
