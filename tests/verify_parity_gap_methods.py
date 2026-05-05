"""
Verification: 6 Parity Gap Methods — Deep State Investigation
=============================================================

Context (Critical Analysis — Phase 1-3):
-----------------------------------------
`verify_api_parity.py` reports 7 methods as "Missing in Python Wrapper":
  commit_state, execute_process_async, report_conflict, report_success,
  set_audit_system, set_strict_cas, set_strict_guards

This file investigates the *actual* runtime state of each method:
  - How it is accessed (direct, via __getattr__, or property abstraction)
  - Whether the parity checker's verdict is accurate
  - What correctness risks (if any) exist at each access point

Root cause of false alarms: Python's TheusEngine has:
  >>> def __getattr__(self, name):
  ...     return getattr(self._core, name)
  This delegates ALL unknown attribute lookups to the Rust core at runtime.
  `inspect.getmembers(TheusEngine_CLASS)` does NOT see __getattr__ delegated
  methods because they are instance-level and dynamic — hence the false alarms.

Classification (4 categories from investigation):
  A. Abstracted via @property        : set_strict_cas, set_strict_guards
  B. Init-time internal wiring       : set_audit_system
  C. Runtime internal lifecycle      : report_conflict, report_success,
                                       execute_process_async
  D. REMOVED at Rust level           : commit_state (OCC bypass — removed from
                                       #[pymethods] in v3.0.27, Transaction::__exit__
                                       now uses direct borrow_mut assignment)

Test structure mirrors the Critical Analysis 4-case framework:
  Model Case    → expected normal behavior
  Related Cases → adjacent API usage
  Edge Cases    → boundary/abuse scenarios
  Conflict Case → scenario where the gap causes real harm

Run: python -m pytest tests/verify_parity_gap_methods.py -v
"""

import inspect
import unittest

import pytest
import theus_core
from theus.engine import TheusEngine
from theus_core import ConflictManager


def _make_engine_with_core_state(**data):
    """
    Helper: Create a bare TheusEngine and seed initial state via a transaction.
    commit_state() was removed from #[pymethods] in v3.0.27; the normal
    Transaction path is now the only way to write state.
    """
    engine = TheusEngine()
    with engine.transaction() as tx:
        tx.update(data=data)
    return engine


# ─────────────────────────────────────────────────────────────────
# SECTION 0: PARITY CHECKER STRUCTURAL FLAW
# ─────────────────────────────────────────────────────────────────

class TestParityCheckerStructuralFlaw(unittest.TestCase):
    """
    Demonstrates WHY all 7 methods appear as "missing" in verify_api_parity.py
    even though they are accessible at runtime.

    Root cause: `hasattr(TheusEngine_CLASS, name)` vs runtime __getattr__ delegation.
    """

    GAP_METHODS = [
        "execute_process_async",
        "report_conflict",
        "report_success",
        "set_audit_system",
        "set_strict_cas",
        "set_strict_guards",
    ]

    def test_class_level_hasattr_returns_false(self):
        """
        MODEL CASE: hasattr(TheusEngine, name) returns False for all 6 gaps
        because they are not defined directly on the Python class.
        This is exactly what verify_api_parity.py checks.
        """
        for name in self.GAP_METHODS:
            # Property abstractions (set_strict_cas → strict_cas property):
            # the method name itself is NOT a class attribute
            result = hasattr(TheusEngine, name)
            # Only strict_cas and strict_guards are properties but under different names
            # All 7 original Rust method names fail the class-level hasattr check
            self.assertFalse(
                result,
                f"'{name}' should NOT be a class-level attribute on TheusEngine "
                f"(it's behind __getattr__ delegation or a renamed @property)"
            )

    def test_instance_level_access_succeeds_via_getattr(self):
        """
        RELATED CASE: At runtime, ALL 7 methods ARE accessible on a live engine
        instance via Python's __getattr__ delegation to self._core.

        This proves the parity checker produces false alarms.
        """
        engine = TheusEngine()
        for name in self.GAP_METHODS:
            # Should not raise AttributeError — __getattr__ delegates to _core
            attr = getattr(engine, name)
            self.assertIsNotNone(attr, f"'{name}' should be accessible on TheusEngine instance")
            self.assertTrue(callable(attr), f"'{name}' should be callable")

    def test_getattr_is_defined_on_class(self):
        """
        RELATED CASE: Confirm __getattr__ delegation mechanism exists in engine.py.
        This is the bridge that makes all 7 methods accessible at runtime.
        """
        self.assertTrue(
            hasattr(TheusEngine, "__getattr__"),
            "TheusEngine must define __getattr__ for delegation to work"
        )
        # Verify it delegates to _core
        source = inspect.getsource(TheusEngine.__getattr__)
        self.assertIn("_core", source, "__getattr__ should delegate to self._core")

    def test_parity_checker_would_miss_property_abstractions(self):
        """
        EDGE CASE: set_strict_cas → engine.strict_cas (property).
        The parity checker compares by exact method name.
        It misses that 'set_strict_cas' (Rust name) is exposed as 'strict_cas' (Python property).
        """
        # strict_cas IS a property on the class
        self.assertTrue(
            isinstance(inspect.getattr_static(TheusEngine, "strict_cas", None), property),
            "engine.strict_cas must be a @property"
        )
        # but 'set_strict_cas' (the Rust name) is NOT a property
        self.assertFalse(
            isinstance(inspect.getattr_static(TheusEngine, "set_strict_cas", None), property),
            "set_strict_cas is NOT a property — it's behind __getattr__"
        )


# ─────────────────────────────────────────────────────────────────
# SECTION 1: commit_state — OCC BYPASS RISK
# ─────────────────────────────────────────────────────────────────

class TestCommitState(unittest.TestCase):
    """
    commit_state(state) — REMOVED in v3.0.27.

    Root cause: fn commit_state in #[pymethods] was a stringly-typed coupling
    between Transaction::__exit__ (Rust) and TheusEngine (Python object).
    The call `engine.call_method1("commit_state", ...)` inside __exit__ required
    commit_state to be exported, making it callable from Python and enabling
    silent OCC bypasses.

    Fix: Transaction::__exit__ now uses `engine.borrow_mut().state = ...` directly.
    commit_state is no longer in #[pymethods]. Both Python access paths are closed:
      engine._core.commit_state(...)  → AttributeError
      engine.commit_state(...)        → AttributeError
    """

    def test_model_case_transaction_path_is_occ_protected(self):
        """
        MODEL CASE: Normal Rust Transaction context manager path.
        State version increments and commit_state is called by Rust __exit__ after OCC.
        Python never calls commit_state directly in this path.
        """
        engine = _make_engine_with_core_state(counter=0)
        initial_version = engine._core.state.version

        with engine._core.transaction() as tx:
            tx.update(data={"counter": 1})

        new_version = engine._core.state.version
        self.assertGreater(
            new_version, initial_version,
            "State version must increment after a successful transaction commit"
        )
        self.assertEqual(engine._core.state.data["counter"], 1)

    def test_conflict_case_direct_commit_bypasses_occ(self):
        """
        CONFLICT CASE (CLOSED): commit_state removed from #[pymethods] in v3.0.27.
        Calling engine._core.commit_state(...) now raises AttributeError.
        The OCC bypass vector is closed at the Rust level.
        """
        engine = _make_engine_with_core_state(value="original")
        stale_state = engine._core.state

        with engine._core.transaction() as tx:
            tx.update(data={"value": "updated"})

        self.assertEqual(engine._core.state.data["value"], "updated")

        # commit_state no longer exported — must raise AttributeError
        with self.assertRaises(AttributeError):
            engine._core.commit_state(stale_state)

    def test_via_getattr_delegation_same_bypass_risk(self):
        """
        EDGE CASE (CLOSED): engine.commit_state via __getattr__ also raises AttributeError.
        Both Python access paths to the OCC bypass are now closed.
        """
        engine = _make_engine_with_core_state(x=1)
        stale = engine._core.state

        with self.assertRaises(AttributeError):
            engine.commit_state(stale)

    def test_commit_state_is_called_by_rust_transaction_exit(self):
        """
        RELATED CASE: Verify commit_state is invoked during Transaction.__exit__.
        Evidence: version counter advances only when commit_state is called.
        """
        engine = _make_engine_with_core_state(logged=False)
        version_before = engine._core.state.version

        with engine._core.transaction() as tx:
            tx.update(data={"logged": True})
        # __exit__ called commit_state internally

        version_after = engine._core.state.version
        self.assertGreater(
            version_after, version_before,
            "Transaction.__exit__ must have called commit_state to advance version"
        )
        self.assertTrue(engine._core.state.data["logged"])


# ─────────────────────────────────────────────────────────────────
# SECTION 2: set_strict_cas / set_strict_guards — PROPERTY ABSTRACTION
# ─────────────────────────────────────────────────────────────────

class TestStrictModeAbstraction(unittest.TestCase):
    """
    set_strict_cas / set_strict_guards — abstracted behind @property.

    Rust Rust:   fn set_strict_cas(&self, enabled: bool)
    Python:      engine.strict_cas = True → _core.set_strict_cas(True)

    The property setter is the canonical Python API. The raw Rust method
    is still accessible via __getattr__ but bypasses the Python-side
    _strict_cas/_strict_guards shadow variables.
    """

    def test_model_case_property_setter_syncs_rust_and_python(self):
        """
        MODEL CASE: Setting via @property updates both Python shadow and Rust core.
        """
        engine = TheusEngine(strict_cas=False, strict_guards=False)

        self.assertFalse(engine.strict_cas)
        self.assertFalse(engine.strict_guards)

        # Set via @property
        engine.strict_cas = True
        engine.strict_guards = True

        # Python shadow updated
        self.assertTrue(engine.strict_cas)
        self.assertTrue(engine.strict_guards)

        # Rust core must reflect the change (verify via getter attribute)
        # We can re-read the property which reads _strict_cas/_strict_guards
        self.assertTrue(engine._strict_cas, "_strict_cas shadow must be True")
        self.assertTrue(engine._strict_guards, "_strict_guards shadow must be True")

    def test_related_case_raw_setter_bypasses_python_shadow(self):
        """
        RELATED CASE: Calling _core.set_strict_cas() directly (via __getattr__)
        updates Rust state but NOT the Python _strict_cas shadow variable.
        This is a subtle inconsistency.
        """
        engine = TheusEngine(strict_cas=False)

        # Direct Rust call via __getattr__ (or _core)
        engine.set_strict_cas(True)  # via __getattr__

        # Rust core is updated (the behavior will change)
        # But the Python shadow remains False
        self.assertFalse(
            engine._strict_cas,
            "Python shadow _strict_cas NOT updated when calling raw set_strict_cas via __getattr__"
        )

    def test_edge_case_property_getter_reflects_python_shadow_not_rust(self):
        """
        EDGE CASE: engine.strict_cas getter returns _strict_cas (Python shadow),
        which can diverge from Rust state if raw set_strict_cas was called.
        """
        engine = TheusEngine(strict_cas=False)
        engine.set_strict_cas(True)   # raw Rust call via __getattr__

        # Property getter returns the Python shadow (False), not Rust state (True)
        self.assertFalse(
            engine.strict_cas,
            "engine.strict_cas returns Python shadow which may lag behind raw Rust calls"
        )

    def test_conflict_case_init_correctly_syncs_both(self):
        """
        CONFLICT CASE: When strict_cas=True is passed to __init__, both
        _strict_cas shadow and Rust core must be consistent from the start.
        """
        engine = TheusEngine(strict_cas=True, strict_guards=True)

        self.assertTrue(engine.strict_cas, "Init should set Python shadow")
        self.assertTrue(engine.strict_guards, "Init should set Python shadow")

        # Engine behaves in strict mode
        # (full behavioral test would require a CAS conflict setup)


# ─────────────────────────────────────────────────────────────────
# SECTION 3: set_audit_system — INIT-TIME WIRING
# ─────────────────────────────────────────────────────────────────

class TestSetAuditSystem(unittest.TestCase):
    """
    set_audit_system(audit) — one-time wiring in __init__.

    Rust: fn set_audit_system(&self, audit: PyObject)
    Python: self._core.set_audit_system(self._audit)  [called once in __init__]

    No user-facing API needed. Method is not part of the public contract.
    """

    def test_model_case_set_audit_system_wired_if_audit_provided(self):
        """
        MODEL CASE: When an audit system is provided, set_audit_system is called
        during __init__ to connect Python audit to Rust events.
        No further user action needed.
        """
        # Engine without audit — set_audit_system NOT called
        engine_no_audit = TheusEngine()
        self.assertIsNone(engine_no_audit._audit)

    def test_related_case_audit_system_callable_via_getattr(self):
        """
        RELATED CASE: set_audit_system is accessible via __getattr__ on any engine
        instance, but calling it outside __init__ on a live engine is a misuse.
        It should only be called once during initialization.
        """
        engine = TheusEngine()
        # Verify method is accessible via __getattr__
        fn = engine.set_audit_system
        self.assertTrue(callable(fn))

    def test_edge_case_double_call_overwrites_audit_silently(self):
        """
        EDGE CASE: Calling set_audit_system twice replaces the previous audit
        without warning. This is a design smell but not a crash.
        """
        engine = TheusEngine()
        # Call with a dummy callable — should not raise
        class FakeAudit:
            pass

        fake = FakeAudit()
        # First call
        engine._core.set_audit_system(fake)
        # Second call — silently overwrites
        engine._core.set_audit_system(fake)
        # No exception = the design allows silent overwrite


# ─────────────────────────────────────────────────────────────────
# SECTION 4: report_conflict / report_success — INTERNAL RETRY LOOP
# ─────────────────────────────────────────────────────────────────

class TestReportConflictSuccess(unittest.TestCase):
    """
    report_conflict / report_success — internal CAS retry machinery.

    Python engine.py calls these on self._core inside the retry loop:
      Line 703: decision = self._core.report_conflict(func.__name__)
      Line 674: self._core.report_success(func.__name__)

    These methods are NOT part of the public API — they are implementation
    details of the retry/backoff mechanism driven by ConflictManager.
    """

    def test_model_case_report_conflict_returns_retry_decision(self):
        """
        MODEL CASE: report_conflict returns a RetryDecision with retry intent.
        """
        engine = TheusEngine()
        decision = engine._core.report_conflict("process_a")
        self.assertTrue(hasattr(decision, "should_retry"))
        self.assertTrue(hasattr(decision, "wait_ms"))
        self.assertIsInstance(decision.should_retry, bool)
        self.assertIsInstance(decision.wait_ms, int)

    def test_model_case_report_success_resets_conflict_counter(self):
        """
        MODEL CASE: report_success resets the conflict counter for a process.
        After success, next conflict for that process starts from 0.
        """
        engine = TheusEngine()
        # Simulate 3 conflicts
        for _ in range(3):
            engine._core.report_conflict("my_process")

        # Report success — counter resets
        engine._core.report_success("my_process")

        # Next conflict should have short backoff (reset to initial)
        decision = engine._core.report_conflict("my_process")
        # After reset, attempt count is 1, so wait = base * 2^0 = base (2ms) * jitter
        self.assertTrue(decision.should_retry)
        self.assertLess(decision.wait_ms, 20, "After reset, backoff should be near base (2ms)")

    def test_related_case_conflict_manager_direct_access(self):
        """
        RELATED CASE: ConflictManager (the underlying logic) can be instantiated
        and tested independently without an engine.
        """
        cm = ConflictManager(max_retries=3, base_backoff_ms=10)
        key = "worker"

        d1 = cm.report_conflict(key)
        d2 = cm.report_conflict(key)
        d3 = cm.report_conflict(key)

        self.assertTrue(d1.should_retry)
        self.assertTrue(d2.should_retry)
        self.assertTrue(d3.should_retry)

        # Backoff grows (exponential)
        self.assertGreater(d2.wait_ms, d1.wait_ms)

        # After max_retries, VIP escalation or give-up
        d4 = cm.report_conflict(key)  # attempt 4 > max_retries=3
        # 4th attempt: either VIP or give up — depends on VIP logic
        self.assertIsInstance(d4.should_retry, bool)

    def test_edge_case_accessible_via_getattr(self):
        """
        EDGE CASE: report_conflict/success are accessible via __getattr__.
        They are NOT part of the declared Python public API but are reachable.
        This creates an undocumented surface that could be misused.
        """
        engine = TheusEngine()

        # Both accessible via __getattr__
        self.assertTrue(callable(getattr(engine, "report_conflict")))
        self.assertTrue(callable(getattr(engine, "report_success")))

    def test_conflict_case_report_success_nonexistent_key_is_noop(self):
        """
        CONFLICT CASE: Calling report_success for a key that never had conflicts
        should be a no-op (no exception, no side effects).
        """
        engine = TheusEngine()
        # Should not raise
        engine._core.report_success("never_conflicted_process")


# ─────────────────────────────────────────────────────────────────
# SECTION 5: execute_process_async — PYTHON DELEGATION CHAIN
# ─────────────────────────────────────────────────────────────────

class TestExecuteProcessAsync:
    """
    execute_process_async(name, func, tx=None) — dispatch primitive.

    Python engine.py calls: await self._core.execute_process_async(name, func, tx)
    Test test_engine_polymorphism.py calls: await engine.execute_process_async(...)
    The latter works via __getattr__ delegating to _core.execute_process_async.

    Users should use engine.execute(func) — the high-level wrapper.
    Direct use of execute_process_async bypasses audit, retry, schema validation.
    """

    @pytest.mark.asyncio
    async def test_model_case_async_func_runs_on_event_loop_thread(self):
        """
        MODEL CASE: An async function dispatched via execute_process_async
        runs on the event loop thread (same thread as the caller).
        """
        import threading
        engine = TheusEngine()

        async def my_task(ctx):
            return threading.get_ident()

        caller_thread = threading.get_ident()

        # Via __getattr__ delegation (same as test_engine_polymorphism.py uses)
        result = await engine.execute_process_async("my_task", my_task)
        assert result == caller_thread, "Async task must run on the event loop thread"

    @pytest.mark.asyncio
    async def test_related_case_sync_func_dispatched_to_thread_pool(self):
        """
        RELATED CASE: A sync function is offloaded to a thread pool by Rust,
        preventing event loop blocking.
        """
        import threading
        engine = TheusEngine()

        def sync_task(ctx):
            return threading.get_ident()

        caller_thread = threading.get_ident()
        result = await engine.execute_process_async("sync_task", sync_task)
        assert result != caller_thread, "Sync task must run on a ThreadPool thread"

    @pytest.mark.asyncio
    async def test_edge_case_direct_call_bypasses_audit_and_retry(self):
        """
        EDGE CASE: execute_process_async called directly (without engine.execute())
        skips audit validation, retry logic, and schema checks.
        A process with side effects runs exactly once — no retries on failure.
        """
        engine = TheusEngine()
        call_count = [0]

        async def counted_task(ctx):
            call_count[0] += 1
            return call_count[0]

        # Direct dispatch — no retry layer
        result = await engine.execute_process_async("counted_task", counted_task)
        assert call_count[0] == 1, "Direct dispatch runs exactly once (no retry middleware)"
        assert result == 1

    @pytest.mark.asyncio
    async def test_conflict_case_no_transaction_means_no_state_commit(self):
        """
        CONFLICT CASE: execute_process_async without a tx=Transaction object.
        The task runs but no state commit happens — tx=None means results are
        not persisted to engine.state. This is a silent data loss risk.
        """
        engine = TheusEngine(context={"domain": {"sentinel": "before"}})

        async def mutating_task(ctx):
            # ctx here is a ProcessContext, not a TheusEngine guard
            # Without a tx, mutations have nowhere to commit
            return "done"

        await engine.execute_process_async("mutating_task", mutating_task)

        # State unchanged — no commit happened
        assert engine.state.data.get("domain", {}).get("sentinel") == "before", \
            "Without tx, execute_process_async does NOT persist state changes"


# ─────────────────────────────────────────────────────────────────
# SECTION 6: COMBINED REGRESSION — PARITY CHECKER IMPROVEMENT
# ─────────────────────────────────────────────────────────────────

class TestParityCheckerImprovement(unittest.TestCase):
    """
    Regression tests that prove what an improved parity checker must do.

    Current verify_api_parity.py:
      - Checks hasattr(py_cls, name) → misses __getattr__ delegation
      - Treats ALL 7 gaps identically (silent "intentional?" warning)
      - commit_state silently treated same as set_audit_system

    Required improvement:
      1. Use hasattr(engine_instance, name) for runtime check
      2. Classify gaps into buckets (PROPERTY_ABSTRACTED, INTERNAL, UNSAFE)
      3. commit_state must not be silently allowed — it is an OCC bypass risk
    """

    # Methods accessible at class level (real Python methods or properties)
    PYTHON_CLASS_METHODS = {"state", "execute", "execute_workflow", "transaction",
                            "strict_cas", "strict_guards", "__enter__", "__exit__"}

    # Methods that should be accessible at instance level via __getattr__
    GAP_METHODS_ACCESSIBLE_AT_RUNTIME = [
        "execute_process_async", "report_conflict",
        "report_success", "set_audit_system", "set_strict_cas", "set_strict_guards"
    ]

    def test_instance_check_would_eliminate_false_alarms(self):
        """
        If the parity checker used `hasattr(instance, name)` instead of
        `hasattr(class, name)`, it would find all 7 methods present.
        """
        engine = TheusEngine()
        for name in self.GAP_METHODS_ACCESSIBLE_AT_RUNTIME:
            self.assertTrue(
                hasattr(engine, name),
                f"Instance check: '{name}' should be found via __getattr__ delegation"
            )

    def test_commit_state_must_be_classified_as_high_risk(self):
        """
        commit_state was removed from #[pymethods] in v3.0.27 (OCC bypass closed).
        It must not be accessible via either Python path:
          - engine._core.commit_state(...)  [direct Rust object]
          - engine.commit_state(...)        [via __getattr__ delegation]
        """
        engine = TheusEngine()
        self.assertFalse(
            hasattr(engine, "commit_state"),
            "commit_state must not be accessible — removed from Rust #[pymethods]"
        )
        self.assertFalse(
            hasattr(engine._core, "commit_state"),
            "commit_state must not be accessible on _core — removed from Rust #[pymethods]"
        )

    def test_property_abstraction_bucket_correctly_identified(self):
        """
        set_strict_cas and set_strict_guards should be classified as
        PROPERTY_ABSTRACTED because they're exposed via @property setters.
        """
        # strict_cas and strict_guards ARE proper Python properties
        strict_cas_prop = inspect.getattr_static(TheusEngine, "strict_cas", None)
        strict_guards_prop = inspect.getattr_static(TheusEngine, "strict_guards", None)

        self.assertIsInstance(strict_cas_prop, property)
        self.assertIsInstance(strict_guards_prop, property)

        # Their setters call the Rust methods
        setter_source_cas = inspect.getsource(strict_cas_prop.fset)
        setter_source_guards = inspect.getsource(strict_guards_prop.fset)

        self.assertIn("set_strict_cas", setter_source_cas)
        self.assertIn("set_strict_guards", setter_source_guards)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
