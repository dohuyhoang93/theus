# Technical Report: Flux Engine Signal Blindness (Design Gap)

**Date:** Jan 2026
**Status:** COMPLETED (Fixed in v3.0.2-patch1)
**Affected Version:** Theus v3.0.2 (Resolved)

## 1. Executive Summary
The Flux DSL Engine (`theus_core::WorkflowEngine`) is currently **incapable of reading Signals** (`sig_*`, `cmd_*`). It can only evaluate conditions based on persistent Domain/Global state. This renders Event-Driven Architectures (EDA) and Reactive AI Loops impossible to implement using purely the Workflow YAML.

**Impact Severity:** HIGH.
**Consequence:** Developers cannot write workflows like "If user clicks stop, then abort". They are forced to hack state variables (`domain.is_stopped`) instead of using ephemeral signals.

---

## 2. Technical Root Cause

The issue lies in the Python-to-Rust bridge within `theus/engine.py`.

### The Code (`theus/engine.py:192`)
```python
# Build context dict for condition evaluation
data = self.state.data
ctx = {
    'domain': data.get('domain', None),
    'global': data.get('global', None),
    # ❌ MISSING: 'signal' or 'cmd'
}

# Execute workflow with process executor callback
executed = wf_engine.execute(ctx, self._run_process_sync)
```

The `WorkflowEngine.execute()` method in Rust expects a `PyObject` (Dict) representing the context. However, the Python Engine filters the context down to only `domain` and `global`. The `signal` zone, even if present in the System State, is deliberately excluded or forgotten during this construction.

---

## 3. Impact Assessment

### ❌ Immediate Impact
*   **Disabled Event-Driven Workflows:** You cannot write:
    ```yaml
    steps:
      - if: signal.cmd_emergency_stop == true
        then: terminate
    ```
*   **State Pollution:** Developers must promote transient signals to Domain state (e.g., `domain.cmd_stop`) just to make them visible to Flux. This violates the "Immutability" and "Clean Domain" principles.

### ❌ Long-term Impact on AI Agents
*   **Reactive Loop Failure:** AI Agents rely heavily on `cmd_interrupt` or `sig_human_feedback`. If the Orchestrator (Flux) cannot see these, the Agent cannot react to human intervention in real-time.

## 4. Technical Deep Dive: Tokio & Signal Lifecycle

It is important to understand that `SIG_` and `CMD_` are not just Python variables; they are **Messages** managed by the Rust Core's Async Runtime.

1.  **Transport (Tokio Channels):** Signals are delivered via `mpsc::channel`. Tokio manages the ordering and delivery guarantees.
2.  **Lifecycle (Ephemeral):** Rust guarantees that signals exist strictly for ONE tick. They are automatically dropped from the HashMap after processing, ensuring zero memory leaks.
3.  **Waking Mechanism:** When a Flux workflow waits for a signal (`wait_signal: cmd_start`), the Tokio Executor "parks" the task. The arrival of the signal triggers a `Waker`, resuming the workflow immediately.

**The Disconnect:** While Rust handles the *transport* perfectly, the *View layer* constructed for the Python `WorkflowEngine` (synchronous evaluator) fails to include these signals in its snapshot.

---

## 5. Implementation Plan (The Fix)

### Phase 1: Rust Core Exposure
*   **Action:** Verify if `State` struct in `theus_core` exposes a public getter for the `signal` map (or a clone of it).
*   **Fallback:** If not exposed, update `theus_core/src/state.rs` to add `get_signals() -> PyObject`.

### Phase 2: Engine Bridge Update (`theus/engine.py`)
*   **Current:**
    ```python
    ctx = {'domain': ..., 'global': ...}
    ```
*   **Target:**
    ```python
    # Inject Signal Zone
    signals = self.state.signals if hasattr(self.state, 'signals') else {}
    ctx = {
        'domain': data.get('domain'), 
        'global': data.get('global'),
        'signal': signals,  # <--- Critical Fix
        'cmd': signals      # Alias for convenience
    }
    ```

### Phase 3: Verification
1.  **Create Test Workflow:** `specs/test_signal_flux.yaml`
    ```yaml
    name: Signal Test
    steps:
      - wait: 1 # Tick
      - if: signal.cmd_activate == true
        then: log "Activated!"
        else: log "Still waiting..."
    ```
2.  **Run Test:** Execute workflow and inject `cmd_activate` via CLI/Script.
3.  **Success Criteria:** Workflow transitions to "Activated" logic branch.

---

## 6. Verification Results (Implemented)

**Date:** Jan 21, 2026
**Fix Implemented:**
1.  **Rust Core (`structures.rs`):** Added `last_signals` map to `State` to latched signals per tick. Exposed via `state.signals` getter.
2.  **Engine (`engine.py`):** Updates `execute_workflow` to inject `signal` dictionary into Flux Context.

**Test Case (`examples/async_outbox`):**
*   **Scenario:** Inject signal `cmd_start_outbox=True` at Tick 0.
*   **Workflow:**
    ```yaml
    - flux: if
      condition: "signal.get('cmd_start_outbox') == 'True'"
      then: [log_success]
      else: [log_failure]
    ```
*   **Result:** `[OK] SIGNAL RECEIVED BY FLUX: cmd_start_outbox detected!`

**Conclusion:** The Flux Signal Blindness is **RESOLVED**. Event-Driven Workflows are now fully supported.

---
*Report generated by Theus Architecture Audit*
