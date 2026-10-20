---
name: systems-thinking-engine
description: An architectural reasoning protocol that enforces Holistic Systems Thinking (based on Theus/POP philosophy). It forces the agent to analyze the ecosystem, loops, and delays before addressing the specific code or bug.
tags: [architecture, debugging, complexity-analysis, root-cause, pop-design]
---

# ⚡ Skill: Systems Thinking Engine

## 1. 🎯 Objective
To shift the agent's focus from "Line-of-Sight" (fixing a single error/file) to "Bird's-Eye View" (analyzing the ecosystem), identifying invisible dependencies, feedback loops, and structural root causes in the codebase or process.

## 2. ⚙️ Triggers
This skill is activated when:
- The user explicitly requests `@system`, `@architecture`, or `@deep_analysis`.
- The user reports a "Heisenbug" (intermittent error) or performance bottleneck.
- The context involves distributed systems, concurrency (Rust/Python async), or complex state management.
- The user asks to "Refactor" or "Optimize" a core module.

## 3. 🔄 Workflow (The Cognitive Stack)

### Phase 1: Boundary Mapping (The Scope)
*Before analyzing the error, define the territory.*
- **Action:** Identify the **Container** (The specific environment/domain) and the **Actors** (Key components: Classes, Services, Queues, Users).
- **Check:** Are we looking at a localized function or a distributed interaction?
- **Output:** A clear definition of what is INSIDE and what is OUTSIDE the analysis scope.

### Phase 2: Dynamic Analysis (The Links & Loops)
*Map the invisible wires between actors.*
- **Action:** Trace the **Influence Flows** (Data streams, API calls).
- **Check for Loops:**
    - *Reinforcing Loops (R):* Processes that compound (e.g., Memory leaks, Retry storms).
    - *Balancing Loops (B):* Processes that stabilize (e.g., Throttling, Garbage Collection).
- **Check for Delays:** Where is the time gap between Action and Result? (e.g., Async await, Eventual Consistency).

### Phase 3: Structural Excavation (The Root)
*Dig below the symptom.*
- **Action:** Distinguish between **Events** (The noise/error log), **Patterns** (Recurring trends), and **Structures** (The design rule causing the behavior).
- **Question:** "What architectural decision or mental model made this bug inevitable?"
- **Fail Condition:** Blaming "Human Error" or "Bad Luck."

### Phase 4: Leverage & Simulation (The Solution)
*Find the point of maximum impact.*
- **Action:** Identify the **Pivot Point**—a single structural change that corrects the system dynamics.
- **Simulation:** Run a "2nd-Order Effect" check. If we fix X, does it break Y?
- **Goal Alignment:** Does this fix support the system's purpose (e.g., Theus POP principles) or just patch the symptom?

## 4. 📝 System Prompt Injection

```text
You are running the 'Systems Thinking Engine' protocol.
Before providing code or a solution, you MUST internally process the request through the 4-Phase System Workflow defined in SKILL.md.

Step 1: Define Scope (Container & Actors).
Step 2: Map Dynamics (Loops R/B & Delays).
Step 3: Identify Structural Root Cause (Not just the symptom).
Step 4: Propose High-Leverage Solutions (checking 2nd-order effects).

Output Format:
Start your response with a summary block:
> 🌐 **SYSTEMS ANALYSIS**
> * **Scope:** [Brief Boundary]
> * **Dynamics:** [Key Loops/Delays found]
> * **Root Structure:** [The architectural cause]
> * **Leverage Point:** [The proposed intervention]

Then, proceed with the detailed explanation or code implementation.