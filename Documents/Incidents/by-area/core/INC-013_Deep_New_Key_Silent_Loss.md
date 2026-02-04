---
id: INC-013
title: Deep New Key Silent Loss
area: core
severity: High
### Status: RESOLVED
**Severity**: High (Silent Data Loss)
**Impact**: Nested object mutations were silently discarded when parent was already shadowed.
**Resolution**: Implemented "Known Shadow" tracking (Double Shadowing Prevention) in Rust Core (`src/proxy.rs`).

## 1. Description
Attempting to assign a new key in a deeply nested dictionary (e.g. `d["a"]["b"]["new"] = 1`) failed silently if `d` was accessed via a `SupervisorProxy`. The proxy for `b` (child of shadow `a`) incorrectly triggered a second Copy-on-Write (`get_shadow`) on `b`, creating a disconnected copy `b'` that received the write, while `a` still pointed to `b`.

### Root Cause
**Double Shadowing Disconnection**: When a Shadow Object is already mutable (part of a transaction), its children are mutable. However, `SupervisorProxy` treated them as "Originals" and requested `get_shadow`. Because the children themselves were not explicitly registered as Shadows in `shadow_cache` (only the root `d` was), `get_shadow` created a NEW shadow instance, breaking the reference graph.

## 6. Resolution Plan (Executed)
1.  **Reproduction:** The file `tests/02_safety/test_chapter_05_compliance.py` confirmed the issue.
2.  **Fix (Rust Core):**
    *   **Architecture Update:** Added `is_shadow` flag to `SupervisorProxy`.
    *   **Logic Change:** If a Proxy wraps a Shadow, it passes `is_shadow=true` to children proxies.
    *   **Guard:** Children proxies skip `get_shadow` logic, preserving the reference to the mutable Shadow Graph.
3.  **Verify:** Re-enabled "Deep New Key" assertion in `test_chapter_05_compliance.py`. **PASSED.**

## 7. Verification Logs
*   **Test Script:** `tests/02_safety/test_chapter_05_compliance.py`
*   **Command:** `py -m pytest tests/02_safety/test_chapter_05_compliance.py`
*   **Result:** 5 passed in 2.80s.
*   **Key Assertion:** `assert engine.state.data["domain"]["user"]["profile"]["new_deep"] == 2` -> **PASSED**.

## 8. Related
*   **Audit:** Chapter 05 Audit

## 8. Integrative Critical Analysis (@integrative-critical-analysis)

> **CORE INSIGHT:** The bug stems from a conceptual misalignment between "Object Identity" (which stayed same) and "Content Value" (which changed), revealing that the `SupervisorProxy` relies too heavily on identity-based dirty checking rather than deep content inspection.

### 1. Critical Dissection
*   **The Trap (False Assumption):** We assumed that recursive `__setitem__` calls automatically bubble "Dirty" status up to the root.
*   **The Truth (Reality):** When `ctx.domain.user["profile"]["new"] = 1` happens:
    1.  `user["profile"]` accesses a Child Proxy.
    2.  The Child Proxy marks *itself* dirty.
    3.  The *Parent Proxy* (`user`) checks `profile`. It sees the **same object identity** (the child dict/proxy).
    4.  The Parent assumes "No Change" because it doesn't deeply re-inspect the *content* of the child unless the child's *identity* was swapped.

### 2. Systemic Context
*   **Breaking Point:** **Deep Dynamic Expansion**. The system handles *Modification* (value change) possibly because it tracks key access, but *Expansion* (new key) falls into a blind spot of the diff engine if the parent doesn't re-scan keys.
*   **Hidden Connection:** This interacts with the **Zero-Copy Optimization**. To avoid expensive deep copies, we rely on "Lazy" checks. This bug is the cost of that optimization—we traded safety for speed and missed a guard rail.

### 3. Strategic Path
*   **The Solution:**
    *   **Short Term:** Force `mark_dirty` propagation to root on ANY write.
    *   **Long Term:** Implement `TrackedDict` in Rust that notifies the Registry of *any* structural change, decoupling "Dirty State" from "Python Object Wrappers".

## 9. Systems Thinking Analysis (@systems-thinking-engine)

> 🌐 **SYSTEMS ANALYSIS**
> * **Scope:** `SupervisorProxy` (Rust/Python Interop) & `StateUpdate` (Commit Logic).
> * **Dynamics:** **Reinforcing Loop (Efficiency):** We optimize for read speed -> use Lazy Proxies -> Complex Write Logic -> Bugs -> More complex Fixes.
> * **Root Structure:** The decision to support **Pythonic Mutability** (OOP style) on top of an **Immutable Core** (Functional style).
> * **Leverage Point:** **Explicit Structure Versioning**. Instead of diffing objects, track a "Structure Version" counter. Any `__setitem__` increments it. Commit checks version.

### Structural Excavation
The "Heisenbug" nature suggests our tests were too "Happy Path". We tested:
1.  `a.b.c = 1` (Update existing) -> Works because key exists in Shadow.
2.  `a.x = 1` (Shallow new) -> Works because Root Proxy catches it.
3.  `a.b.x = 1` (Deep new) -> **Fails** because the "Bridge" (b) didn't tell "Root" (a) that "b" has a new shape.

## 10. Intellectual Virtue Auditor (@intellectual-virtue-auditor)

> **Objective:** To purge bias and ensure epistemic integrity in our failure analysis.

### 🛡️ Filter A: Intellectual Humility (The Knowledge Limit)
*   **Check:** Did we claim "100% Accuracy" too early?
*   **Correction:** Yes. We claimed "Confirmed 100% via Test" after passing 4 scenarios, assuming these covered the *entire* state space of dictionary mutations. We failed to acknowledge that `SupervisorProxy` is a leaky abstraction over Rust.
*   **Truth:** We only verified that *declared* features work. we did not verify that *undeclared* standard Python behaviors (like recursive new keys) were preserved.

### 🛡️ Filter B: Intellectual Courage ( The Unpopular Truth)
*   **Check:** Are we avoiding the hard truth about the Architecture?
*   **Correction:** The "Zero-Copy Lazy Proxy" architecture is **fragile by design**. It trades correctness for speed. Admitting this is uncomfortable because it suggests we might need a heavy refactor (TrackedDict) rather than a quick patch.
*   **Verdict:** We must face the possibility that "Transparent Mutation" might be an unachievable ideal without significant performance cost.

### 🛡️ Filter C: Intellectual Empathy (Steel-manning the Bug)
*   **Check:** Why did the original developer write it this way?
*   **Analysis:** The developer wasn't "lazy". They were maximizing **Read Performance**. A recursive "Dirty Check" on every write would destroy the Zero-Copy benefit for large datasets (e.g., AI Tensors). The current "Identity Check" is a rational optimization for *stable* schemas, just not for *dynamic* ones.

### 🛡️ Filter D: Intellectual Integrity (No Double Standards)
*   **Check:** Do we demand strictness from Users but allow laxity in Core?
*   **Correction:** We force users to declare `inputs/outputs` rigidly (Chapter 05), yet the Core itself fails to strictly track all mutations.
*   **Action:** We must hold the Core to the same "Iron Discipline" we preach. If the Core cannot guarantee persistence, it should **Error Out** rather than silently lose data.

### 🛡️ Filter E: Intellectual Perseverance (Depth)
*   **Check:** Did we stop at "It's a bug"?
*   **Action:** We dug deeper to find the *mechanism* (Identity vs Value). We verified it's not just a "missing line of code" but a fundamental behavior of the Proxy wrappers.

### 🛡️ Filter F: Confidence in Reason (Logic over Hope)
*   **Check:** Are we hoping a "quick fix" will work?
*   **Logic:** A quick fix (e.g., `parent.mark_dirty()`) solves the *symptom* for one level. But logic dictates this applies recursively. If we fix it for `depth=2`, will it fail for `depth=3`?
*   **Conclusion:** Only a recursive or event-bubbling solution is logically sound.

### 🛡️ Filter G: Intellectual Autonomy (First Principles)
*   **Check:** Are we just copying pattern from other frameworks?
*   **Analysis:** Most ORMs use "Dirty Tracking". Theus uses "Shadow Copies". We must evaluate this from *our* First Principles (POP - Process Oriented Programming). In POP, state is a snapshot. Therefore, *any* divergence from the snapshot MUST be captured.

### 🛡️ Filter H: Fair-mindedness (Bias Check)
*   **Check:** Are we downplaying this to make the Audit look successful?
*   **Correction:** We marked this as Severity **HIGH**. We are not hiding it. We formally requested `INC-013`.

**Final Verified Verdict:** The system has a critical blind spot in Deep Dynamic Expansion. This is not just a bug; it is an architectural tradeoff that failed silently. Immediate mitigation is required.
