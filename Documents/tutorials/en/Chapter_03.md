# Chapter 3: Transaction Discipline

> [!CAUTION]
> **DISCIPLINE REQUIRED:** Changing a variable in Theus is a formal request, not an instant action. You must choose the right tool for the job.

## The Hierarchy of Needs (Mental Model)

To avoid "brain overload," structure your thinking into three tiers. You only need the top tier for 99% of your work.

### 🔻 Tier 1: The "Daily Driver" (95% Usage)
*   **Method 1:** **Implicit POP (`@process` decorator)** → "I just return the new value."
*   **Method 2:** **Safe Edit (`engine.edit()`)** → "Safe context manager for complex mutations outside processes."
*   **Complexity:** 🟢 Easy & Recommended

### 🔻 Tier 2: The "Setup Tool" (5% Usage)
*   **Method:** **Batch Transaction (`tx.update`)** → "Initializing the system or importing bulk data."
*   **Complexity:** 🟡 Medium

### 🔻 Tier 3: The "Kernel" (System Internals Usage)
*   **Method:** **Explicit CAS (`compare_and_swap`)**
*   **Mindset:** "I am building a primitive lock or a high-concurrency counter."
*   **Complexity:** 🔴 Hard (Requires Strict/Smart mode selection)

---

---

## 1. Implicit POP (Recommended)
This is the "Magical" way, but it works because it follows strict rules. You declare **what you want to change** in the decorator, and simply **return the new value**.

```python
@process(outputs=['domain.cart']) # Contract: "I will update the cart"
def add_item_process(ctx):
    # 1. Read
    cart = ctx.domain.cart.copy()
    
    # 2. Modify (Local)
    cart.total += 10
    
    # 3. Return (Theus handles the Transaction)
    return cart
```
*   **Why it's safe:** Theus wraps your function in a loop. If `domain.cart` changes while you run (Conflict), Theus re-runs your function automatically.
*   **Limitation:** You can only return values that match your `outputs`.

## 2. Batch Transaction (`tx.update`)
Use this when you are "outside" a process (e.g., inside `main.py` setup) or need to update many unrelated things at once.

```python
# Explicitly open a transaction batch
with engine.transaction() as tx:
    # This prepares a commit. Nothing changes in Rust yet.
    tx.update(data={
        "domain": {
            "config": {"mode": "dark"},
            "users": [...] 
        }
    })
# On exit: Theus sends the batch to Rust.
```
*   **Benefit:** In v3.0.22, this performing a **Recursive Deep Merge**. If you provide a partial dictionary, Theus merges it into the existing state, preserving sibling fields.


## 3. Safe Edit (`engine.edit()`)
This is the most idiomatic way to handle complex state changes in Setup scripts, API handlers, or Unit Tests.

```python
with engine.edit() as ctx:
    # Mutate directly using Pythonic syntax
    ctx.domain.order.status = "PAID"
    ctx.domain.inventory['Laptop'] -= 1
    # Siblings like 'payment' or 'other_items' are 100% safe.
```
*   **Type Safety:** If you gõ sai tên thuộc tính (e.g., `ctx.domain.oreder`), Python sẽ báo `AttributeError` ngay lập tức.
*   **Auto-Rollback:** Nếu có Exception xảy ra bên trong block `edit()`, toàn bộ thay đổi sẽ bị hủy bỏ, bảo vệ trạng thái hệ thống.

## 4. Explicit CAS (`compare_and_swap`)

Used for building low-level primitives or high-concurrency systems.
Theus v3 offers two flavors of CAS, controlled by `strict_cas`.

### A. Smart CAS (Default: `strict_cas=False`)
*Field-Level Concurrency (Simpler, Safer)*

The Engine is smart. If you try to update `domain.counter` but someone else updated `domain.name`, the Engine sees **no conflict** and allows your update.

```python
# 1. Get current version
ver = engine.state.version

# 2. Try to update
# Succeeds if:
# - Version matches exactly OR
# - Only unrelated fields have changed
result = engine.compare_and_swap(ver, {"domain": {"counter": 101}})
```

### B. Strict CAS (`strict_cas=True`)
*Version-Level Audit (Hard Mode)*

Reject if *anything* changed. Use this for banking or critical audit logs where the "World State" must be exactly what you saw.

### Decision Matrix

| Scenario | Use Method | Why? |
| :--- | :--- | :--- |
| **Business Logic** | Implicit POP | Safest. Automatic retries. |
| **Setup / Batch** | Transaction | Efficient. One version bump. |
| **High Concurrency** | Smart CAS | Merges non-conflicting updates. |
| **Strict Audit** | Strict CAS | Zero tolerance for state drift. |

## Summary
1.  Use **Implicit POP** (`return value`) for almost everything.
2.  Use **Batch Transaction** for Setup/Init.
3.  Avoid **Explicit CAS** unless you enjoy pain.

---
**Next:** Now we can talk about designing your Processes properly.
-> **[Chapter 04: Processes & Contracts](./Chapter_04.md)**
