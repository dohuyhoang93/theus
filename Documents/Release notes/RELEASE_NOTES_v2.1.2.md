# Release Notes v2.1.2

## 🚀 Performance Updates

### 1. Workflow Caching (Crucial Fix)
*   **Problem:** Before v2.1.2, `TheusEngine` re-read and parsed the YAML workflow file from disk for *every single step* of the process. In large-scale simulations (e.g., 5000 episodes * 200 steps * 5 agents), this caused millions of redundant I/O operations, severely impacting performance.
*   **Solution:** Implemented `workflow_cache` in `TheusEngine`. Workflow files are now read once and cached in memory.
*   **Impact:** Drastic reduction in I/O overhead and significantly faster execution times for long-running agents.

### 2. Parallel Orchestration Support
*   While not a direct change to the Framework core, the framework is verified to support `ThreadPoolExecutor` for running parallel instances of the Engine, enabling multi-core simulation runs in the consuming applications (like EmotionAgent).

## 📦 Improvements
*   Updated internal logic to ensure `execute_workflow` is thread-safe for reading from the new cache.

---
*Release Date: 2025-12-23*
