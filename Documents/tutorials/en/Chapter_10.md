# Chapter 10: Performance Optimization & Memory Management

Performance in Theus is a balance between **Safety (Transactional Integrity)** and **Speed (Raw Access)**. This chapter guides you through optimizing Theus for high-load scenarios like Deep Learning Training.

## 1. Level 1 Optimization: "Heavy Zone" (Granular)
**Best for:** Hybrid systems (e.g., Robot with critical safety logic + Vision AI).

In standard logic, Theus "Shadow Copies" lists and dicts. For a 1GB Tensor, this is fatal.
Soluton: Prefix variable names with `heavy_`.

```python
@dataclass
class VisionDomain(BaseDomainContext):
    # Standard (Protected, Rollback-capable)
    counter: int = 0
    
    # HEAVY ASSET (Bypasses Shadow Copy)
    heavy_camera_frame: np.ndarray = field(...)
    heavy_q_table: dict = field(...)
```

*   **Behavior:** Theus passes the **Direct Reference** to the process.
*   **Trade-off:** Zero Copy speed, but **No Rollback** for that specific field.

## 2. Level 2 Optimization: Strict Mode Toggle (Global)
**Best for:** Pure AI Training, Simulations (Gym/GridWorld), where speed is #1 and crash recovery is handled by restarting the episode.

You can disable the entire Transactional layer of Theus.

```python
# In run_experiments.py
engine = TheusEngine(
    system_ctx, 
    strict_mode=False  # <--- THE MAGIC SWITCH
)
```

### What happens when `strict_mode=False`?
1.  **Zero Overhead:** No Transaction objects created. No Audit Log history.
2.  **Pass-through Guards:** `ContextGuard` becomes a transparent proxy. Reading/Writing happens directly on the real object.
3.  **Contract Enforcement:** Disabled. You can modify undeclared variables (Side Effects possible).
4.  **Rollback:** Disabled. If a process crashes, the Context is left in a "Dirty" state.
5.  **Silent Mode:** "Unsafe Mutation" warnings (modifying context without a lock) are suppressed (moved to DEBUG level) to keep logs clean during high-speed loops.

## 3. Comparison Matrix

| Feature | Default (`True`) | Heavy Zone | Strict Mode `False` |
| :--- | :--- | :--- | :--- |
| **Shadow Copy** | Yes (Safe) | No (Direct) | No (Direct) |
| **Rollback** | Yes (Full) | Scalar: Yes, Heavy: No | **No** (None) |
| **Audit Logs** | Yes (Ephemeral) | Yes | **No** (None) |
| **Memory Usage** | High (History) | Low | **Lowest** |
| **Use Case** | Production / Finance | Robotics / Hybrid AI | **Training / Sim** |

## 4. Avoiding Memory Leaks
Even with optimizations, Python references can leak.
*   **Restart Strategy:** For long training (1M+ episodes), restart the worker process periodically to clear fragmented memory.
*   **Avoid "God Objects":** Don't put everything in one giant List/Dict. Use specific dataclasses.
