# Chapter 22: Inside Theus Engine - Transaction Mechanism (MVCC)

How does Theus provide ACID transactions, Rollback, and Isolation while allowing Python to hold onto objects? The answer lies in a hybrid **Rust-Python MVCC (Multi-Version Concurrency Control)** architecture.

This chapter demystifies the Core.

## 1. The Ownership Model: "Rust Supervisors, Python Owners"

Unlike frameworks that convert Python data into Rust structs (serialization overhead), Theus Rust Core **DOES NOT** own the data content.

*   **Rust State:** Holds `HashMap<String, Arc<PyObject>>`. It stores **pointers** (References) to objects living in the Python Heap.
*   **Zero-Copy Logic:** When Rust needs to access data, it borrows the pointer back to Python. No data conversion happens.

## 2. The Transaction Lifecycle

When a non-Pure process starts, Theus initiates a Transaction. Here is the exact sequence of events:

### Step 1: Snapshot (Reference Copying)
The `ProcessContext` is created with a reference to the current Global State Version (e.g., v100). This involves cloning `Arc` pointers (cheap), not cloning data.

### Step 2: Access Interception (Lazy Shadowing)
The process receives a `SupervisorProxy` (via `ContextGuard`).
*   **Read Access:** The Proxy delegates directly to the original object (Reference A).
*   **Write Access (First Time):** When `__setattr__` or `__setitem__` is called (or a mutable getter like `list` access):
    1.  `ContextGuard` triggers `transaction.get_shadow(original_obj)`.
    2.  This performs a **DEEP COPY** of *only* that specific object tree (using `copy.deepcopy`). 
    3.  This creates **Reference B** (Shadow Copy).
    4.  The Proxy is updated to point to Reference B.

**Result:** The Process is now working on a private Shadow Copy (B). The Global State still points to A. (Isolation).

### Step 3: Delta Logging
Every modification to Reference B is tracked in the `Transaction` struct buffer:
```rust
pending_data[path] = Reference_B;
```

### Step 4: Optimistic Commit (Pointer Swapping)
When the process finishes (`__exit__`), Theus attempts to commit:
1.  **Conflict Check:** Verifies if Global State is still at v100 (or if modified keys don't conflict).
2.  **State Update:** `State.update()` creates a new State struct (v101).
3.  **Pointer Swap:** In v101, the pointer for `domain` is updated from A to B.
    *   `State_v100.domain` -> Ref A
    *   `State_v101.domain` -> Ref B

### Step 5: Rollback (Discard)
If an exception occurs or conflict is detected:
*   The Transaction drops Reference B.
*   The Global State remains pointing to Ref A (v100).
*   Reference B is cleaned up by Python's Garbage Collector.

## 3. Why is this Powerful?

1.  **Performance:** We only copy what you touch (Lazy). If you read 1GB of data but write 1KB, only the 1KB structure is copied (conceptually, though deepcopy granularity depends on object structure).
2.  **Safety:** Global State is immutable. You cannot accidentally corrupt the state of other running processes because you are writing to a Shadow.
3.  **Python Native:** Because the data stays in Python Heap, you can use any Python library (Numpy, Pandas, Pydantic) inside the state. Rust doesn't need to know the schema.

## 4. Visualizing the Pointer Swap

```
[Initial State v1]
   "domain" ----> [Object A (Python Heap)]

[Transaction Start]
   Process View -> Proxy wraps [Object A]

[Process Modifies 'domain']
   ContextGuard: "Stop! Creating Shadow..."
   [Object A] --deepcopy--> [Object B (Shadow)]
   Process View -> Proxy wraps [Object B]
   Process modifies [Object B] values.

[Commit Success]
   [New State v2]
      "domain" ----> [Object B]   <-- STATE UPDATED

[Old State v1] (Held by slow readers)
   "domain" ----> [Object A]   <-- OLD VERSION PRESERVED
```

This mechanism (Pointer Swapping + CoW) allows Theus to achieve high-performance concurrency in Python without the GIL locking the entire state during logic execution.
