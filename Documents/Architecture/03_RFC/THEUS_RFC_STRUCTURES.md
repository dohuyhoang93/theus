# RFC: Comprehensive Upgrade for Theus Tracked Structures (Rust Core)

## 1. Problem Statement
The current Python implementation of `TrackedDict` and `TrackedList` in `theus.structures` relies partially on Python's `MutableMapping` and `MutableSequence` mixins. This leads to:
1.  **Compliance Issues:** `TrackedDict` crashes on `.clear()` due to missing `popitem()`. `TrackedList` lacks in-place `sort()` and `reverse()`.
2.  **Performance & Audit Bloat:** Mixin-based `clear()` iterates and deletes items one-by-one, generating N `REMOVE` log entries instead of a single `RESET` entry.
3.  **Leaky Abstractions:** Developers cannot use these structures as true drop-in replacements for standard Python types.

## 2. Proposal: Full Protocol Implementation via PyO3
Move all tracked structures to Rust using `#[pyclass]` and implement full protocols.

### 2.1. TrackedDict (Mapping Protocol)
See previous RFC for details. Added focus on `clear()` implementation.

### 2.2. TrackedList (Sequence Protocol)
Must implement all methods of `list` to be a true replacement.

```rust
#[pyclass]
pub struct TrackedList {
    inner: Vec<PyObject>,
    dirty: bool,
}

#[pymethods]
impl TrackedList {
    // --- Mutating Methods (Optimized) ---
    
    fn append(&mut self, item: PyObject) -> PyResult<()> {
        self.inner.push(item);
        self.dirty = true;
        // Log "APPEND"
        Ok(())
    }

    fn extend(&mut self, iterable: &Bound<'_, PyAny>) -> PyResult<()> {
        // Efficiently extend from iterator
        // Log "EXTEND" (Single entry)
        Ok(())
    }

    fn insert(&mut self, index: isize, item: PyObject) -> PyResult<()> {
        // Standard insert logic
        // Log "INSERT"
        Ok(())
    }

    fn remove(&mut self, value: PyObject) -> PyResult<()> {
        // Find and remove first occurrence
        // Log "REMOVE"
        Ok(())
    }

    fn pop(&mut self, index: isize) -> PyResult<PyObject> {
        // Remove at index
        // Log "POP"
        Ok(val)
    }

    fn clear(&mut self) -> PyResult<()> {
        self.inner.clear();
        self.dirty = true;
        // Log "RESET" (Single entry) -> Crucial optimization
        Ok(())
    }

    fn sort(&mut self, key: Option<PyObject>, reverse: bool) -> PyResult<()> {
        // In-place sort using Python comparison
        // self.dirty = true;
        // Log "SORT" (or "REORDER")
        Ok(())
    }

    fn reverse(&mut self) -> PyResult<()> {
        self.inner.reverse();
        self.dirty = true;
        // Log "REORDER"
        Ok(())
    }

    // --- Dunder Methods ---
    fn __len__(&self) -> usize { self.inner.len() }
    fn __getitem__(&self, index: isize) -> PyResult<PyObject> { ... }
    fn __setitem__(&mut self, index: isize, item: PyObject) -> PyResult<()> { ... }
    fn __delitem__(&mut self, index: isize) -> PyResult<()> { ... }
    fn __contains__(&self, item: PyObject) -> bool { ... }
    fn __iter__(&self, py: Python) -> PyResult<PyObject> { ... }
}
```

## 3. Implementation Strategy: The "Dirty" Flag
Instead of triggering expensive Rust-to-Python calls for every operation, we use a simple `dirty` boolean in Rust.
The `Transaction` manager in Rust checks this flag at the end of a "process" step to decide if diffing/serialization is needed.
For granular audit logging (Undo/Redo), operations must still log directly to the Transaction buffer.

## 4. Frozen Structures
## 5. Advanced Considerations

### 5.1. Nested Dirty Propagation
When a tracked structure contains another tracked structure (e.g., `TrackedList` inside `TrackedDict`), a mutation in the leaf node must propagate the "dirty" state upwards to the root.
**Mechanism:**
- Each Tracked Structure holds a `Weak` reference to its parent.
- When `mark_dirty()` is called, it recursively calls `parent.mark_dirty()` until root.
- This ensures the `TransactionManager` (watching the root) detects changes even deep within the tree.

### 5.2. Thread Safety (Concurrency)
Since Theus operates in a Multi-Agent environment (often threaded), shared context structures must be thread-safe.
**Rust Implementation:**
- Wrap internal storage in `Arc<RwLock<...>>` instead of raw `HashMap`/`Vec`.
- `Arc` allows shared ownership across threads.
- `RwLock` allows multiple readers (efficient for observation) but exclusive writer (safe for mutation).
- This prevents race conditions during simultaneous logging or state updates from multiple agents.
