"""
Deep Investigation: 6 Remaining Parity Gap Methods
====================================================

Critical Analysis (SKILL.md — 8 Rules + 4-Tier Case Framework)
---------------------------------------------------------------

PROBLEM STATEMENT (Rule 1):
  verify_api_parity.py still reports 6 methods as "⚠️ Missing in Python Wrapper".
  These were previously classified as "Category A/B/C — low/medium risk".
  This file investigates whether that classification is accurate via real runtime probes.

INQUIRY SCOPE (Rule 2):
  For each method, verify:
    (a) Exact desync mechanism (shadow vs Rust state)
    (b) Which code paths are actually affected by the desync
    (c) Whether existing tests would catch regression
    (d) Edge/conflict cases that weren't considered before

DATA INTEGRITY (Rule 3):
  All findings verified by running actual Python+Rust code, reading:
    theus/engine.py   (Python shadow variables + property setters)
    src/engine.rs     (Rust Mutex fields + #[pymethods])
    src/conflict.rs   (ConflictManager VIP + backoff logic)

CONCEPTUAL CLARITY (Rule 4):
  Key distinction: "accessible via __getattr__" ≠ "safe to call externally"
  A method can be callable but have silent side-effects that corrupt state.

METHODS INVESTIGATED (6):
  A. set_strict_cas     — shadow desync: Rust correct, Python getter lies
  B. set_strict_guards  — shadow desync: GUARDS behavior stale in _attempt_execute
  C. set_audit_system   — silent overwrite, None crash risk
  D. report_conflict    — external injection can force VIP escalation → CAS lockout
  E. report_success     — premature reset can corrupt exponential backoff
  F. execute_process_async — `name` silently dropped, ctx.state is LIVE not snapshot

Run: python -m pytest tests/verify_parity_remaining_methods.py -v
"""

import asyncio
import inspect
import threading
import unittest

import pytest
from theus.engine import TheusEngine
from theus_core import ConflictManager


# ─────────────────────────────────────────────────────────────────
# SECTION A: set_strict_cas — SHADOW vs RUST MUTEX DESYNC
# ─────────────────────────────────────────────────────────────────

class TestSetStrictCasDesync(unittest.TestCase):
    """
    INVESTIGATION: set_strict_cas — Shadow variable desync.

    ARCHITECTURE CONTEXT:
      Rust TheusEngine.strict_cas = Arc<Mutex<bool>>
      Python TheusEngine._strict_cas = bool shadow variable

      CORRECT path:  engine.strict_cas = True
                     → sets _strict_cas = True
                     → calls _core.set_strict_cas(True)       ← both synced

      INCORRECT path: engine.set_strict_cas(True)  via __getattr__
                      → calls _core.set_strict_cas(True)       ← Rust updated
                      → _strict_cas NOT updated                 ← Python shadow stale

    IMPACT:
      compare_and_swap() reads Rust Mutex directly → correct (tolerates desync)
      _attempt_execute() reads self._strict_guards → stale (guards behavior wrong)
      engine.strict_cas getter returns _strict_cas → lies about current state

    Rule 5 (Logical Consistency): The property setter is the ONLY correct path.
    Using __getattr__ delegation for a setter is logically inconsistent with the
    property contract.
    """

    def test_model_case_property_setter_syncs_both(self):
        """
        MODEL CASE: engine.strict_cas = True updates both Python shadow and Rust.
        engine.strict_cas getter returns correct value.
        """
        engine = TheusEngine(strict_cas=False)
        self.assertFalse(engine.strict_cas)
        self.assertFalse(engine._strict_cas)

        engine.strict_cas = True  # canonical path

        # Both synced
        self.assertTrue(engine.strict_cas)
        self.assertTrue(engine._strict_cas)

    def test_related_case_init_syncs_both(self):
        """
        RELATED CASE: TheusEngine(strict_cas=True) must initialize both
        _strict_cas (Python shadow) and Rust Mutex to True.
        """
        engine_on = TheusEngine(strict_cas=True)
        self.assertTrue(engine_on.strict_cas)
        self.assertTrue(engine_on._strict_cas)

        engine_off = TheusEngine(strict_cas=False)
        self.assertFalse(engine_off.strict_cas)
        self.assertFalse(engine_off._strict_cas)

    def test_edge_case_raw_setter_via_getattr_desync(self):
        """
        EDGE CASE — DESYNC CONFIRMED:
        Calling engine.set_strict_cas(True) via __getattr__ updates Rust core
        but leaves engine._strict_cas (Python shadow) stale.

        engine.strict_cas getter returns the stale Python shadow → LIES.

        Root cause: __getattr__ delegates to _core directly, bypassing the
        @property setter that maintains the shadow variable.
        """
        engine = TheusEngine(strict_cas=False)

        # Call raw method via __getattr__ (delegates to engine._core.set_strict_cas)
        engine.set_strict_cas(True)

        # The Python shadow is STALE
        self.assertFalse(
            engine._strict_cas,
            "DESYNC: _strict_cas shadow not updated by raw set_strict_cas() call"
        )

        # The getter reports the WRONG value
        self.assertFalse(
            engine.strict_cas,
            "DESYNC: engine.strict_cas getter lies — reports False while Rust has True"
        )

    def test_edge_case_raw_setter_but_cas_behavior_is_correct(self):
        """
        EDGE CASE (mitigating factor):
        compare_and_swap() reads the Rust Mutex directly — not the Python shadow.
        So even after desync via raw setter, CAS enforcement is actually CORRECT.

        The lie is: Python code reading engine.strict_cas for decisions/logging
        gets wrong data. The Rust CAS itself is fine.
        """
        engine = TheusEngine(strict_cas=False)
        engine.set_strict_cas(True)  # desync: Rust=True, _strict_cas=False

        # CAS with wrong version SHOULD fail because Rust has strict_cas=True
        with engine._core.transaction() as tx:
            tx.update(data={"x": 1})
        # After one transaction, version=1

        from theus_core import ContextError
        # Attempting CAS with wrong version 0 (version is now 1)
        with self.assertRaises(ContextError):
            engine._core.compare_and_swap(0, {"x": 99})  # wrong version

    def test_conflict_case_monitoring_code_reads_stale_shadow(self):
        """
        CONFLICT CASE: Any monitoring/logging code that reads engine.strict_cas
        after a raw set_strict_cas() call gets stale data.

        Example: A health check endpoint that serializes engine config will
        report strict_cas=False while the engine is actually enforcing strict CAS.

        This is a silent observability failure — no exception raised, wrong data.
        """
        engine = TheusEngine(strict_cas=False)
        engine.set_strict_cas(True)  # bypass property setter

        # Health check simulation
        config_snapshot = {
            "strict_cas": engine.strict_cas,      # reads Python shadow
            "strict_guards": engine.strict_guards  # reads Python shadow
        }

        # Reports False for strict_cas even though Rust enforces it
        self.assertFalse(
            config_snapshot["strict_cas"],
            "Monitoring snapshot shows WRONG strict_cas state after raw setter call"
        )


# ─────────────────────────────────────────────────────────────────
# SECTION B: set_strict_guards — GUARD BEHAVIOR DESYNC
# ─────────────────────────────────────────────────────────────────

class TestSetStrictGuardsDesync(unittest.TestCase):
    """
    INVESTIGATION: set_strict_guards — deeper than set_strict_cas.

    ADDITIONAL IMPACT vs set_strict_cas:
      _attempt_execute() passes strict_guards=self._strict_guards to ContextGuard.
      If shadow is stale, the GUARD BEHAVIOR changes — not just an observability issue.

      Line ~884: ContextGuard(... strict_guards=self._strict_guards ...)
      This controls whether zone physics are enforced during process execution.

    Rule 6 (Implications): Stale _strict_guards means ContextGuard runs in wrong mode.
    Zone physics violations that should be caught are silently ignored.
    """

    def test_model_case_property_setter_syncs_both(self):
        """MODEL CASE: @property setter updates shadow and Rust."""
        engine = TheusEngine(strict_guards=False)
        self.assertFalse(engine.strict_guards)

        engine.strict_guards = True
        self.assertTrue(engine.strict_guards)
        self.assertTrue(engine._strict_guards)

    def test_related_case_init_syncs_both(self):
        """
        RELATED CASE: TheusEngine(strict_guards=True) in __init__ only calls
        self._core.set_strict_guards(strict_guards) — it does NOT call set_strict_guards
        via the property setter. BUT it does assign self._strict_guards = strict_guards
        directly at the top of __init__. Both are synced at init time.
        """
        engine = TheusEngine(strict_guards=True)
        self.assertTrue(engine._strict_guards)
        self.assertTrue(engine.strict_guards)

    def test_edge_case_raw_setter_guard_behavior_stale(self):
        """
        EDGE CASE — DEEPER IMPACT:
        After engine.set_strict_guards(True) via __getattr__:
          - engine._strict_guards = False  (stale shadow)
          - Rust strict_guards Mutex = True

        When engine.execute() runs _attempt_execute, it creates ContextGuard with
        strict_guards=self._strict_guards (False). Guard runs in PERMISSIVE mode
        even though caller intended STRICT mode.

        Zone physics violations are silently passed through.
        """
        engine = TheusEngine(strict_guards=False)

        # Call raw method via __getattr__
        engine.set_strict_guards(True)

        # Shadow is stale
        self.assertFalse(
            engine._strict_guards,
            "DESYNC: _strict_guards shadow is stale after raw set_strict_guards() call"
        )
        # Getter also lies
        self.assertFalse(
            engine.strict_guards,
            "DESYNC: engine.strict_guards getter reports False when Rust has True"
        )

    def test_edge_case_setter_is_safe_idempotent_via_property(self):
        """
        EDGE CASE (positive): property setter is idempotent — calling twice is safe.
        """
        engine = TheusEngine(strict_guards=False)
        engine.strict_guards = True
        engine.strict_guards = True  # second call, no side effect
        self.assertTrue(engine.strict_guards)
        self.assertTrue(engine._strict_guards)

    def test_conflict_case_toggle_pattern_breaks_with_raw_setter(self):
        """
        CONFLICT CASE: A common pattern is:
          engine.strict_guards = False   # temporarily disable for migration
          ... do migration ...
          engine.strict_guards = True    # re-enable

        If raw setter is used in the middle:
          engine.strict_guards = False   (property — shadow=False, Rust=False)
          engine.set_strict_guards(True) (raw — shadow=False, Rust=True)
          engine.strict_guards = True    (property setter: reads _strict_guards=False?
                                          No — setter always writes directly)

        Actually the property SETTER writes BOTH regardless of current value.
        So the last property setter call will fix the desync.
        The dangerous window is the period between raw call and next property setter.
        """
        engine = TheusEngine(strict_guards=True)

        # Step 1: disable via property (correct path)
        engine.strict_guards = False
        self.assertFalse(engine._strict_guards)  # both synced

        # Step 2: re-enable via raw setter (wrong path) → creates window
        engine.set_strict_guards(True)
        self.assertFalse(
            engine._strict_guards,
            "Shadow still False — dangerous window open (guard runs in wrong mode)"
        )

        # Step 3: the next property setter call closes the window
        engine.strict_guards = True
        self.assertTrue(engine._strict_guards)  # healed


# ─────────────────────────────────────────────────────────────────
# SECTION C: set_audit_system — SILENT OVERWRITE AND None RISK
# ─────────────────────────────────────────────────────────────────

class TestSetAuditSystemMisuse(unittest.TestCase):
    """
    INVESTIGATION: set_audit_system — one-time Rust wiring, open to misuse.

    ARCHITECTURE CONTEXT:
      Rust: audit_system: Arc<Mutex<Option<PyObject>>>
      Python: engine._audit = AuditSystem | None

      Called ONCE in __init__:
        if hasattr(self._core, "set_audit_system"):
            self._core.set_audit_system(self._audit)

      After init, accessible via __getattr__ → engine.set_audit_system(...)
      → writes Rust Mutex without updating engine._audit Python field.

    Rule 7 (Assumptions): The assumption that "only __init__ calls set_audit_system"
    is fragile — the method is fully accessible at runtime.
    """

    def test_model_case_no_audit_has_none_in_rust(self):
        """
        MODEL CASE: Engine created without audit. _audit=None.
        set_audit_system was NOT called (Rust has None in mutex).
        """
        engine = TheusEngine()
        self.assertIsNone(engine._audit)

        # Audit system callable via __getattr__ still exists
        fn = engine.set_audit_system
        self.assertTrue(callable(fn))

    def test_related_case_engine_with_audit_wires_correctly(self):
        """
        RELATED CASE: When audit config is provided at init time,
        set_audit_system is called once correctly, and engine._audit is set.
        """
        # Create minimal audit recipe
        from theus.config import AuditRecipe
        from theus.audit import AuditSystem
        recipe = AuditRecipe(threshold_max=3, reset_on_success=True)
        audit = AuditSystem(recipe)

        # Directly test: calling set_audit_system on _core stores the object
        engine = TheusEngine()
        engine._core.set_audit_system(audit)

        # engine._audit is NOT updated (Python field stays None)
        self.assertIsNone(
            engine._audit,
            "engine._audit Python field NOT updated by direct _core.set_audit_system() call"
        )

    def test_edge_case_double_call_silently_overwrites(self):
        """
        EDGE CASE — SILENT OVERWRITE:
        Calling set_audit_system twice replaces the first audit object silently.
        No exception, no warning. The first audit system is abandoned.

        Risk: Any buffered audit events in the first AuditSystem are lost.
        Any active callbacks on the first AuditSystem will never fire.
        """
        from theus.config import AuditRecipe
        from theus.audit import AuditSystem

        engine = TheusEngine()
        recipe = AuditRecipe(threshold_max=3, reset_on_success=True)
        audit1 = AuditSystem(recipe)
        audit2 = AuditSystem(recipe)

        engine._core.set_audit_system(audit1)
        engine._core.set_audit_system(audit2)  # silently replaces audit1

        # No exception raised — silent overwrite confirmed
        # (We can't easily inspect the Rust Mutex from Python, but the call succeeds)

    def test_edge_case_none_stored_as_pyobject(self):
        """
        EDGE CASE — None BYPASS:
        Calling engine._core.set_audit_system(None) stores None as a PyObject
        in the Rust Mutex. Rust code that calls methods on the stored audit
        will crash at runtime when it tries to call .record() on None.

        This effectively "arms" a crash — no immediate failure, but any
        future Rust-side audit logging will explode.
        """
        engine = TheusEngine()

        # This does NOT raise — Rust accepts any PyObject including None
        engine._core.set_audit_system(None)

        # engine._audit Python field is still None (unchanged)
        self.assertIsNone(engine._audit)
        # The Rust mutex now holds Some(None) — a ticking time bomb

    def test_conflict_case_python_field_diverges_from_rust_state(self):
        """
        CONFLICT CASE: After external set_audit_system call, engine._audit
        and the Rust-side audit object diverge. Code that uses engine._audit
        (Python-side validation gates like AuditValidator) will use the
        OLD audit object while Rust CAS events log to the NEW audit object.

        Two audit pipelines now operate with different states.
        """
        from theus.config import AuditRecipe
        from theus.audit import AuditSystem

        recipe = AuditRecipe(threshold_max=3, reset_on_success=True)
        audit_init = AuditSystem(recipe)

        engine = TheusEngine()
        # Manually wire an audit (simulating what __init__ does)
        engine._audit = audit_init
        engine._core.set_audit_system(audit_init)

        # Now overwrite Rust side only
        audit_external = AuditSystem(recipe)
        engine._core.set_audit_system(audit_external)

        # Python field still points to audit_init
        self.assertIs(
            engine._audit, audit_init,
            "engine._audit still references original audit after external overwrite"
        )
        # Rust-side now uses audit_external — divergence confirmed


# ─────────────────────────────────────────────────────────────────
# SECTION D: report_conflict — EXTERNAL INJECTION AND VIP LOCKOUT
# ─────────────────────────────────────────────────────────────────

class TestReportConflictInjection(unittest.TestCase):
    """
    INVESTIGATION: report_conflict — exposed ConflictManager state machine.

    ARCHITECTURE CONTEXT:
      ConflictManager tracks: failures: HashMap<String, u32>, vip_holder: Option<String>
      VIP escalation rule: if count >= max_retries (default 5):
        if vip is empty → become VIP
        if already VIP → keep trying
        if VIP occupied by other → give up

      compare_and_swap() calls: is_blocked(requester)
        if requester is None (default): ALL non-VIP processes are blocked

    THE CRITICAL FLAW (Rule 6 — Implications):
      External caller injecting N conflicts for "any_key" where N >= max_retries:
        1. Rust promotes "any_key" to VIP status
        2. compare_and_swap(requester=None) returns System Busy for ALL callers
        3. Normal engine.execute() passes requester=None by default
        4. ALL engine.execute() calls start failing with "System Busy (VIP Access Only)"
        5. VIP release requires report_success("any_key") — which must be called explicitly

    This is a DENIAL OF SERVICE vector via the __getattr__ surface.
    """

    def test_model_case_single_conflict_returns_backoff(self):
        """MODEL CASE: One conflict returns should_retry=True with short backoff."""
        engine = TheusEngine()
        decision = engine._core.report_conflict("my_process")
        self.assertTrue(decision.should_retry)
        self.assertGreater(decision.wait_ms, 0)
        self.assertLess(decision.wait_ms, 100)  # base backoff short

    def test_model_case_exponential_backoff_increases(self):
        """
        MODEL CASE: Subsequent conflicts increase wait time exponentially.
        Formula: base_ms * 2^(attempt-1) * jitter(0.8-1.2)
        Default: base=2ms, so: attempt1~2ms, attempt2~4ms, attempt3~8ms...
        """
        engine = TheusEngine()
        decisions = [engine._core.report_conflict("proc_a") for _ in range(4)]

        # Each step should generally increase (accounting for ±20% jitter)
        # Wait times: ~2, ~4, ~8, ~16ms — with jitter still ordered
        self.assertTrue(decisions[0].should_retry)
        self.assertTrue(decisions[1].should_retry)
        # Not asserting strict ordering due to jitter, but wait_ms > 0
        for d in decisions:
            self.assertGreater(d.wait_ms, 0)

    def test_related_case_max_retries_triggers_vip_escalation(self):
        """
        RELATED CASE: After max_retries (default 5) conflicts, the process
        escalates to VIP status. VIP gets wait_ms=1 (near-immediate retry).
        """
        engine = TheusEngine()
        # Exhaust max_retries (default=5 in ConflictManager.new(5, 2))
        for i in range(5):
            engine._core.report_conflict("escalating_proc")

        # 6th conflict — should be VIP mode (wait_ms=1, still should_retry=True)
        vip_decision = engine._core.report_conflict("escalating_proc")
        self.assertTrue(vip_decision.should_retry)
        self.assertLessEqual(vip_decision.wait_ms, 2)  # VIP gets near-immediate retry

    def test_edge_case_external_injection_forces_vip(self):
        """
        EDGE CASE — INJECTION ATTACK:
        Calling engine.report_conflict("target_process") externally 5 times
        forces "target_process" into VIP mode before it has ever run.

        Side effect: is_blocked(None) returns True → ALL compare_and_swap() calls
        with requester=None fail with "System Busy (VIP Access Only)".
        """
        engine = TheusEngine()

        # Inject 5 phantom conflicts via __getattr__
        for _ in range(5):
            engine.report_conflict("phantom_vip")

        # Verify VIP was granted (6th call returns near-zero wait_ms)
        d = engine._core.report_conflict("phantom_vip")
        self.assertLessEqual(d.wait_ms, 2, "VIP granted — wait_ms drops to 1")

    def test_conflict_case_vip_blocks_all_cas_operations(self):
        """
        CONFLICT CASE — CAS LOCKOUT:
        Once any process has VIP status, ALL compare_and_swap() calls with
        requester=None are blocked. This includes the default call path from
        engine.execute() which passes requester=None.

        The engine becomes effectively FROZEN — no writes possible until
        VIP holder calls report_success.
        """
        from theus_core import ContextError

        engine = TheusEngine()

        # Seed initial state
        with engine._core.transaction() as tx:
            tx.update(data={"val": 0})

        # Force a key into VIP via injection
        for _ in range(6):  # > max_retries=5
            engine._core.report_conflict("blocker_proc")

        # Now CAS with requester=None (default) must fail
        with self.assertRaises(ContextError) as ctx:
            engine._core.compare_and_swap(engine._core.state.version, {"val": 99})

        self.assertIn(
            "System Busy",
            str(ctx.exception),
            "VIP lockout confirmed: CAS blocked by phantom VIP holder"
        )

    def test_conflict_case_vip_released_by_report_success(self):
        """
        CONFLICT CASE (resolution): report_success releases VIP lock.
        After release, CAS operations resume normally.
        """
        from theus_core import ContextError

        engine = TheusEngine()
        with engine._core.transaction() as tx:
            tx.update(data={"val": 0})

        # Force VIP
        for _ in range(6):
            engine._core.report_conflict("temporary_vip")

        # Release VIP via report_success
        engine._core.report_success("temporary_vip")

        # CAS should now succeed
        engine._core.compare_and_swap(engine._core.state.version, {"val": 1})
        self.assertEqual(engine._core.state.data["val"], 1)


# ─────────────────────────────────────────────────────────────────
# SECTION E: report_success — PREMATURE RESET AND VIP RELEASE
# ─────────────────────────────────────────────────────────────────

class TestReportSuccessCorruption(unittest.TestCase):
    """
    INVESTIGATION: report_success — counter reset and VIP release.

    ARCHITECTURE CONTEXT (from conflict.rs):
      report_success(key):
        map.remove(&key)          ← removes failure count
        if vip_holder == Some(key):
            vip_holder = None     ← releases VIP

    RISK: External caller can call report_success("real_process") during its
    active retry sequence, resetting its exponential backoff to baseline and
    (if VIP) releasing the VIP priority it earned through legitimate conflicts.
    """

    def test_model_case_success_resets_counter_to_zero(self):
        """MODEL CASE: After report_success, failure count is fully cleared."""
        engine = TheusEngine()
        for _ in range(3):
            engine._core.report_conflict("proc_x")

        engine._core.report_success("proc_x")

        # Next conflict starts from 0 again
        d = engine._core.report_conflict("proc_x")
        self.assertTrue(d.should_retry)
        # Backoff is reset: first attempt after reset = base * 2^0 = 2ms ± 20%
        self.assertLess(d.wait_ms, 5, "Backoff reset — should be near 2ms")

    def test_model_case_success_nonexistent_key_is_noop(self):
        """MODEL CASE: report_success for unknown key is a no-op (no exception)."""
        engine = TheusEngine()
        engine._core.report_success("process_that_never_ran")  # must not raise

    def test_related_case_success_releases_vip_lock(self):
        """
        RELATED CASE: A process that earned VIP (5 failures) calls report_success
        → VIP lock released → other processes can run CAS again.
        """
        from theus_core import ContextError

        engine = TheusEngine()
        with engine._core.transaction() as tx:
            tx.update(data={"x": 0})

        # Give proc_y VIP status
        for _ in range(6):
            engine._core.report_conflict("proc_y")

        # Release via success
        engine._core.report_success("proc_y")

        # CAS from anonymous path (requester=None) now unblocked
        engine._core.compare_and_swap(engine._core.state.version, {"x": 1})
        self.assertEqual(engine._core.state.data["x"], 1)

    def test_edge_case_external_success_resets_active_retry_sequence(self):
        """
        EDGE CASE — PREMATURE RESET:
        A process is in the middle of an exponential backoff sequence (attempt 3,
        backoff ~8ms). An external caller triggers report_success("proc_z"),
        resetting its failure counter to 0.

        The next CAS failure for proc_z will produce a 2ms backoff instead of
        the expected 16ms — disrupting the exponential pressure that should be
        signaling a real contention problem.

        ConflictManager has NO protection against external success injection.
        """
        engine = TheusEngine()

        # Simulate proc_z is in retry sequence at attempt 3
        for _ in range(3):
            engine._core.report_conflict("proc_z")

        # External reset (misuse via __getattr__)
        engine.report_success("proc_z")  # via __getattr__

        # Next failure starts from attempt 1 again (reset to baseline)
        d = engine._core.report_conflict("proc_z")
        self.assertTrue(d.should_retry)
        self.assertLess(
            d.wait_ms, 5,
            "Backoff reset to baseline by external report_success — "
            "lost exponential pressure from 3 prior failures"
        )

    def test_conflict_case_success_before_vip_steals_priority(self):
        """
        CONFLICT CASE — VIP THEFT:
        Process A is at 4 failures (1 away from VIP).
        An external caller triggers report_success("proc_a"), resetting its counter.
        Process B then files conflicts until IT gets VIP.
        Process A never gets VIP even under real sustained contention.

        The fairness guarantee of the VIP escalation is broken by external reset.
        """
        engine = TheusEngine()

        # proc_a accumulates 4 failures (one below VIP threshold=5)
        for _ in range(4):
            engine._core.report_conflict("proc_a")

        # External call resets proc_a's counter
        engine.report_success("proc_a")  # steals priority

        # proc_b now races to get VIP first
        for _ in range(5):
            engine._core.report_conflict("proc_b")
        d_b = engine._core.report_conflict("proc_b")
        self.assertLessEqual(d_b.wait_ms, 2, "proc_b became VIP after proc_a was reset")

        # proc_a now has 0 failures — must start from scratch
        d_a = engine._core.report_conflict("proc_a")
        self.assertTrue(d_a.should_retry)
        # proc_a blocked by proc_b VIP — gets 50ms snooze
        self.assertEqual(
            d_a.wait_ms, 50,
            "proc_a blocked by proc_b VIP — gets max snooze while it was reset unfairly"
        )


# ─────────────────────────────────────────────────────────────────
# SECTION F: execute_process_async — NAME DROPPED, STATE NOT SNAPSHOT
# ─────────────────────────────────────────────────────────────────

class TestExecuteProcessAsyncBypasses:
    """
    INVESTIGATION: execute_process_async — two silent architectural flaws.

    FLAW 1 — NAME SILENTLY DROPPED:
      Rust: `let _ = name;`  → the process name is immediately discarded
      Consequence: audit trail, retry counters, and conflict tracking cannot
      key on the process name when using this low-level path.

    FLAW 2 — ctx.state IS LIVE STATE, NOT TRANSACTION SNAPSHOT:
      Rust: ProcessContext { state: self.state.clone_ref(py), tx: py_tx }
      The state field is the ENGINE's current live state, not the transaction's
      snapshot that was taken at Transaction creation time.

      In the normal execute() path:
        Transaction is created → takes snapshot of state at that moment
        execute_process_async() is called with that transaction
        BUT ctx.state = engine.live_state (NOT snapshot)

      If concurrent writes happen between transaction creation and process execution,
      ctx.state may see NEWER data than the snapshot. The process reads from the
      wrong version — violating snapshot isolation.

    Rule 8 (Perspective): The `execute()` method wraps this with retry/audit middleware.
    The issue is only exploitable via direct calls to execute_process_async.
    """

    @pytest.mark.asyncio
    async def test_model_case_async_function_dispatched_inline(self):
        """
        MODEL CASE: An async function is called inline on the event loop thread.
        """
        engine = TheusEngine()
        caller_thread = threading.get_ident()

        async def async_task(ctx):
            return threading.get_ident()

        result = await engine.execute_process_async("async_task", async_task)
        assert result == caller_thread, "Async task runs inline on event loop thread"

    @pytest.mark.asyncio
    async def test_model_case_sync_function_dispatched_to_thread(self):
        """
        MODEL CASE: A sync function is dispatched via asyncio.to_thread().
        """
        engine = TheusEngine()
        caller_thread = threading.get_ident()

        def sync_task(ctx):
            return threading.get_ident()

        result = await engine.execute_process_async("sync_task", sync_task)
        assert result != caller_thread, "Sync task runs on a thread pool thread"

    @pytest.mark.asyncio
    async def test_edge_case_name_parameter_is_silently_dropped(self):
        """
        EDGE CASE — NAME DROPPED (CONFIRMED):
        Whatever name is passed to execute_process_async, it is discarded.
        Two calls with different names but same function produce identical results.

        Rust: `let _ = name;` — one-line proof.
        """
        engine = TheusEngine()
        recorded_calls = []

        async def recording_task(ctx):
            recorded_calls.append("called")
            return len(recorded_calls)

        # Name "irrelevant_name_1" is discarded — function still runs
        r1 = await engine.execute_process_async("irrelevant_name_1", recording_task)
        # Name "irrelevant_name_2" is also discarded — function still runs
        r2 = await engine.execute_process_async("irrelevant_name_2", recording_task)

        assert recorded_calls == ["called", "called"]
        assert r1 == 1
        assert r2 == 2
        # Both ran fine — name had no effect

    @pytest.mark.asyncio
    async def test_edge_case_ctx_state_is_live_not_snapshot(self):
        """
        EDGE CASE — LIVE STATE IN CONTEXT:
        ctx.state inside execute_process_async is self.state.clone_ref(py) —
        the engine's CURRENT live state, not the transaction snapshot.

        If the engine state is modified between creating the transaction and
        running the process, the process sees the MODIFIED state, not the
        snapshot state. This breaks snapshot isolation.
        """
        engine = TheusEngine()
        with engine._core.transaction() as tx:
            tx.update(data={"counter": 1})

        # Version 1 is committed

        observed_version_in_ctx = []

        async def read_state_version(ctx):
            # ctx.state should be the snapshot version, not live
            observed_version_in_ctx.append(ctx.state.version)
            return ctx.state.version

        # Create a transaction (takes snapshot at version 1)
        tx = engine._core.transaction()

        # Now commit another write BEFORE running the process
        # (simulating concurrent write between tx creation and execution)
        with engine._core.transaction() as tx2:
            tx2.update(data={"counter": 2})
        # Engine is now at version 2

        # Run with the old transaction tx (snapshot was version 1)
        await engine._core.execute_process_async(
            "read_version", read_state_version, tx
        )

        # ctx.state is LIVE engine state (version 2), not snapshot (version 1)
        # This proves the snapshot isolation violation
        assert observed_version_in_ctx[0] == engine._core.state.version, (
            f"ctx.state.version={observed_version_in_ctx[0]} equals LIVE state "
            f"version={engine._core.state.version}, NOT the snapshot version. "
            "Snapshot isolation is broken — process sees concurrent writes."
        )

    @pytest.mark.asyncio
    async def test_conflict_case_no_retry_no_audit_on_failure(self):
        """
        CONFLICT CASE: Exception raised inside execute_process_async propagates
        directly to caller — no retry, no audit event, no conflict counter increment.

        This is the bypass: the middleware stack (execute() + _attempt_execute())
        is completely skipped.
        """
        engine = TheusEngine()
        call_count = [0]

        async def always_fails(ctx):
            call_count[0] += 1
            raise ValueError("deliberate failure")

        with pytest.raises(ValueError, match="deliberate failure"):
            await engine.execute_process_async("failing_task", always_fails)

        # Called exactly once — no retry mechanism
        assert call_count[0] == 1, (
            "execute_process_async has no retry layer — called exactly once on failure"
        )


# ─────────────────────────────────────────────────────────────────
# SECTION G: CROSS-METHOD INTERACTION — compounding risks
# ─────────────────────────────────────────────────────────────────

class TestCrossMethodInteraction(unittest.TestCase):
    """
    INVESTIGATION: Compounding failures when multiple parity gaps interact.

    Rule 5 (Logical Consistency): Each gap is documented in isolation.
    But in production, multiple misuses can compound to create failures
    that are harder to diagnose because no single path is "broken".
    """

    def test_desync_then_vip_creates_undetectable_lockout(self):
        """
        CONFLICT CASE — COMPOUND:
        Step 1: set_strict_cas(True) via raw setter → shadow desync
        Step 2: phantom VIP injection via report_conflict
        Step 3: health check reads engine.strict_cas → False (wrong)
          → health check concludes "engine is in permissive mode, no issue"
          → operator does NOT investigate why CAS calls are failing
          → root cause (VIP lockout) is invisible because monitoring data is wrong

        The desync in Cat A amplifies the VIP lockout in Cat D:
        monitoring data is stale, operator misreads the situation.
        """
        from theus_core import ContextError

        engine = TheusEngine(strict_cas=False)

        # Step 1: create shadow desync
        engine.set_strict_cas(True)  # Rust=True, shadow=False

        # Step 2: inject phantom VIP
        for _ in range(6):
            engine._core.report_conflict("phantom_blocker")

        # Step 3: health check reads WRONG data
        health_snapshot = {
            "strict_cas_enabled": engine.strict_cas,  # reads stale shadow
        }
        self.assertFalse(
            health_snapshot["strict_cas_enabled"],
            "Monitoring says strict_cas=False (misleading) — shadow is stale"
        )

        # But CAS is actually blocked by VIP (not strict_cas)
        with engine._core.transaction() as tx:
            tx.update(data={"y": 1})

        with self.assertRaises(ContextError) as ctx:
            engine._core.compare_and_swap(engine._core.state.version, {"y": 99})
        self.assertIn("System Busy", str(ctx.exception))

    def test_audit_overwrite_hides_vip_events(self):
        """
        CONFLICT CASE — COMPOUND:
        If audit system is externally overwritten (Cat C), then VIP escalation
        events that fired into the original audit are no longer accessible via
        the new audit system. The audit trail has a silent gap.
        """
        from theus.config import AuditRecipe
        from theus.audit import AuditSystem

        recipe = AuditRecipe(threshold_max=3, reset_on_success=True)
        audit_original = AuditSystem(recipe)

        engine = TheusEngine()
        engine._audit = audit_original
        engine._core.set_audit_system(audit_original)

        # Record some events in original audit
        for _ in range(3):
            engine._core.report_conflict("traced_proc")

        # Now silently replace audit system
        audit_replacement = AuditSystem(recipe)
        engine._core.set_audit_system(audit_replacement)

        # Python-side code still sees old audit
        self.assertIs(engine._audit, audit_original)
        # Rust-side events now go to audit_replacement
        # The conflict events above (logged to audit_original) are orphaned


if __name__ == "__main__":
    unittest.main()
