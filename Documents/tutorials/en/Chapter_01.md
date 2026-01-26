# Chapter 1: Theus is NOT Objects

> [!CAUTION]
> **READ THIS FIRST:** Theus is **not** an Object-Oriented Framework. If you try to write "Pythonic" OOP code here, your application will crash, lose data, or perform poorly.

## 1. The Impedance Mismatch
Most Python frameworks (Django, Flask, standard scripts) treat data as **Living Objects** in memory.
```python
# Standard Python (State is alive)
user = User(name="Alice")
user.activate() # Method call mutates state inside the object
print(user.is_active) # True
```

**Theus is different.** Ideally, you should think of Theus like a **Database that speaks Python**.
```python
# Theus (State is dead data in Rust)
state = eng.state.domain # This is a SNAPSHOT (Copy), not the data itself.
user = state.users[0]    # This is a COPY of the data at this instant.

user.activate()          # You just mutually a LOCAL COPY.
# The real data in Rust has NOT changed.
```

## 2. The Physical Reality: Zero-Copy
Theus is built on a **Rust Core** designed for High-Concurrency (1000+ Agents).
*   **Rust State:** A highly optimized `HashMap<String, Value>` protected by Atomic Locks.
*   **Python Context:** When you access `ctx.domain`, Theus gives you a **View** into that map.

### The "Snapshot" Trap
When you read a variable, you are taking a **Snapshot**.
```python
# Timeline of a Bug
order = ctx.domain.orders[0] # Snapshot at T=0
# ... heavy processing (100ms) ...
# Meanwhile, another process DELETES this order at T=50.

order.status = "PAID"        # You are modifying a Ghost.
ctx.domain.orders[0] = order # CRASH! IndexOutOfBounds or Zombie Write.
```

## 3. The Golden Rule
> **"Treat Python Objects as READ-ONLY Snapshots."**

To modify state, you must explicitly **COMMIT** a Transaction. You are not "changing variables"; you are "requesting a state transition".

### Wrong Way (OOP Thinking)
```python
def process_payment(ctx):
    # Trying to use object methods
    ctx.domain.cart.add_item("Apple") 
    ctx.domain.cart.total += 10
    # Result: NOTHING happens. Theus ignores in-place mutations of objects.
```

### Right Way (Transactional Thinking)
```python
def process_payment(ctx):
    # 1. Read (Snapshot)
    cart = ctx.domain.cart.copy()
    
    # 2. Compute (Logic)
    cart.add_item("Apple")
    cart.total += 10
    
    # 3. Commit (Replace)
    return cart 
```
*Note: We will explore simpler ways to do this later, but you must understand this fundamental friction first.*

## 4. Why Use Theus?
If it's so strict, why use it?
*   **Safety:** The locking mechanism prevents Race Conditions that would corrupt a standard Python script instantly.
*   **Scale:** Rust manages the memory. Python just handles the logic. This allows 1000 agents to share 10GB of state with Zero-Copy overhead.

---
**Next:** Now that you know Objects are a lie, let's talk about the cost of moving data between Python and Rust.
-> **[Chapter 02: The Cost of Serialization](./Chapter_02.md)**
