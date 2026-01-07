# Chapter 16: Optimization - The Heavy Zone

For AI Agents, moving large Tensors or Image Blobs through a Transactional System can be expensive.
Theus v2.2 introduces the **Heavy Zone** to solve this.

## 1. The Cost of Transactions
Normally, every time you modify `ctx.data`, Theus:
1.  Creates a Shadow Copy.
2.  Logs the change (Undo Log) to support Rollback.
3.  Merges it back on Commit.

For a 500MB Tensor, this "Copy-on-Write" is too slow.

## 2. The Heavy Zone Solution
If you name your variable starting with `heavy_` (e.g., `heavy_tensor`, `heavy_frame`), Theus treats it differently:

-   **Direct Write:** It bypasses the Transaction Log.
-   **No Undo:** If the transaction fails (Rollback), changes to `heavy_` variables are **LOST** (reverted to original pointer) or inconsistent.
-   **Audit:** Still enforced for safety.

## 3. When to use?
-   **USE FOR:** Large Tensors, Raw Video Frames, Binary Blobs.
-   **DO NOT USE FOR:** Financial State, Counters, Flags, Business Logic variables.

## 4. Example
```python
@process(inputs=['global'], outputs=['global.heavy_image'])
def process_frame(ctx):
    # This write is FAST (No Undo Log)
    ctx.global_ctx.heavy_image = load_massive_image()
```

If this process fails later, `heavy_image` might still point to the new data (dirty write) or be lost depending on memory management, but Theus guarantees the *rest* of the system rolls back correctly.
