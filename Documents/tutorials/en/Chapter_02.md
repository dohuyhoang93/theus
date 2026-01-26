# Chapter 2: The Cost of Serialization

> [!CAUTION]
> **PERFORMANCE WARNING:** Every time you move data between Rust and Python, you pay a tax. Pydantic is not free.

## 1. The Bridge Metaphor
Imagine Theus as two islands connected by a bridge:
*   **Island A (Rust):** Stores raw data (JSON/MsgPack). Fast, strict, efficient.
*   **Island B (Python):** Runs logic (Objects, Classes). Flexible, slow, memory-heavy.
*   **The Bridge (Serialization):** Pydantic / Serde.

Every time you say `eng.state.domain`, a fleet of trucks (Serialization) carries data across the bridge.

### The Cost
```python
# Bad Pattern: High-Frequency Crossing
for i in range(1000):
    user = ctx.domain.users[i] # CROSERVING BRIDGE 1000 TIMES!
    if user.is_active: ...
```
This is slow because Theus has to:
1.  Find the data in Rust Map.
2.  Serialize it to Bytes.
3.  Send to Python.
4.  Python parses Bytes -> Dict -> Pydantic Model.
5.  **Multiply by 1000.**

### The Fix: Bulk Crossing
```python
# Good Pattern: Single Crossing
all_users = ctx.domain.users # Crosses once, getting the whole list.
for user in all_users:       # Pure Python loop (Fast).
    if user.is_active: ...
```

## 2. "The Lost Default" Trap
One of the most dangerous side effects of this Bridge is that **Rust does not know your Python Class definitions.**

### Scenario
You define a user with a default value:
```python
class User(BaseModel):
    name: str
    is_admin: bool = False # Default
```

You initialize the state with an empty dict in `main.py` (lazy developer):
```python
# Initializing Rust State
eng.compare_and_swap(0, {"domain": {"user_1": {"name": "Bob"}}})
# Note: We didn't send 'is_admin'. We assumed Python would add it.
```

### The Crash
1.  Rust stores: `{"name": "Bob"}`. It knows nothing about `is_admin`.
2.  Python Process A reads `user_1`. Pydantic inflates it. `is_admin` becomes `False` (added by Pydantic constructor). **It looks fine.**
3.  **BUT**, if Process B accesses the raw data (e.g., via a pure dictionary path or another language binding), `is_admin` is MISSING.
4.  If Process A saves it back without `exclude_unset=False`, the default might be lost again depending on config.

> **Rule:** Always initialize your State explicitly with full Objects, not partial Dicts.

```python
# Correct Initialization
init_user = User(name="Bob") # Pydantic adds defaults here.
eng.compare_and_swap(0, {"domain": {"user_1": init_user.model_dump()}})
```

## 3. "Type Amnesia"
Rust stores "JSON-compatible" types.
*   Python `datetime` -> Rust `String` ("2024-01-01")
*   Python `set` -> Rust `Array`

When you read it back:
```python
t = ctx.domain.timestamp # It's a String now!
print(t.year) # AttributeError!
```
**Solution:** You must handle re-hydration (converting String back to DateTime) manually in your logic, or use the `Pydantic` model's strict typing to force conversion on read.

## 4. The `edit()` Illusion (A Concrete Example)
The `engine.edit()` method is the perfect example of this Split-Brain problem.

When you do this:
```python
with engine.edit() as ctx:
    ctx.domain.counter = 999
```
You are **ONLY** modifying the Python object (`ctx`). The Rust Core (the true owner) has no idea this happened.

To make this work, Theus has to perform a "Magic Sync" behind the scenes when you exit the `with` block:
1.  **Serialize** the entire affected context (expensive!).
2.  **Force Push** it to Rust, blindly overwriting the version.

> **Lesson:** `edit()` is convenient for tests, but it is an *illusion* powered by expensive serialization. Never use it in production loops.

---
**Next:** How to modify data safely using Transactions.
-> **[Chapter 03: Transaction Discipline](./Chapter_03.md)**
