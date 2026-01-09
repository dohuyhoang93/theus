# Chapter 7: Mutable Pitfalls & Tracked Structures

Working with Lists and Dicts in a Transactional environment is where most "Gotchas" occur. This chapter helps you avoid them.

## 1. TrackedList & TrackedDict
When you access `ctx.domain_ctx.items` (declared in `outputs`), Theus does not return a normal list. It returns `TrackedList`.
This is a "Smart Wrapper" wrapping the Shadow Copy.

**Rule:** Never check `type(ctx.domain_ctx.items) == list`. Use `isinstance(..., list)`.

## 2. The "Zombie Proxy" Hazard
This is the most common newbie mistake.

```python
# WRONG CODE
my_temp = ctx.domain_ctx.items  # Save reference of TrackedList to outside variable
# ... Process ends, Transaction Commit/Rollback ...

# In another Process or next run:
my_temp.append("Ghost") # ERROR! Reference is Stale/Detached.
```

**Why?**
When Transaction ends, the Shadow Copy that `my_temp` holds is either:
- Merged into original (Commit).
- Or destroyed (Rollback).
`my_temp` now points to void or Stale Data. Theus v2 (Strict Mode) actively blocks modification of stale proxies, but it's best not to create them.

**Advice:** Always access directly `ctx.domain_ctx.items` when needed. Do not cache it in local variables for too long.

## 3. FrozenList (Immutable)
If you only `inputs=['domain_ctx.items']` (no output):
- You get `FrozenList`.
- `FrozenList` still shares data with original list (to save RAM), but it blocks all Write APIs.
- This is how Theus saves performance: No Copy needed if you only Read.

---
**Exercise:**
Try creating a global variable `G_CACHE = []` in python file.
In process 1: `G_CACHE = ctx.domain.items`.
After process 1 finishes, try accessing `G_CACHE` externally. Observe if data inside is still consistent with current `sys_ctx.domain.items`?
