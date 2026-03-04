"""
Test Flux DSL: FSM States & Observers — 4-Case Coverage
Covers: Standard, Related, Boundary, Conflict
"""

import pytest
from theus_core import WorkflowEngine, FSMState


class TestFluxFSM4Case:
    """4-Case test coverage for Flux FSM state machine."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    def test_fsm_initial_state_pending(self):
        """State should be Pending before execute()."""
        yaml_content = """
steps:
  - process: noop
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        assert engine.fsm_state == FSMState.Pending

    def test_fsm_transitions_to_complete(self):
        """Successful execute → Pending → Running → Complete."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        engine.execute({}, lambda n: None)
        assert engine.fsm_state == FSMState.Complete

    def test_fsm_state_history_recorded(self):
        """Full history: [Pending, Running, Complete]."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        engine.execute({}, lambda n: None)

        history = engine.state_history
        assert history == [FSMState.Pending, FSMState.Running, FSMState.Complete]

    # ================================================================
    # RELATED (Liên quan)
    # ================================================================

    def test_fsm_observer_called_on_transition(self):
        """Observer receives (old_state, new_state) on each transition."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        transitions = []
        engine.add_state_observer(lambda old, new: transitions.append((old, new)))

        engine.execute({}, lambda n: None)

        # Expect: Pending→Running, Running→Complete
        assert len(transitions) == 2
        assert transitions[0] == (FSMState.Pending, FSMState.Running)
        assert transitions[1] == (FSMState.Running, FSMState.Complete)

    def test_fsm_multiple_observers(self):
        """All registered observers are called."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        log_a = []
        log_b = []
        engine.add_state_observer(lambda o, n: log_a.append(n))
        engine.add_state_observer(lambda o, n: log_b.append(n))

        engine.execute({}, lambda n: None)

        assert log_a == [FSMState.Running, FSMState.Complete]
        assert log_b == [FSMState.Running, FSMState.Complete]

    def test_fsm_observer_exception_does_not_crash(self):
        """Observer throwing exception should not crash the engine."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        # NOTE: Observer throws, but engine should swallow it
        engine.add_state_observer(lambda o, n: (_ for _ in ()).throw(ValueError("bad observer")))

        # Should not raise
        engine.execute({}, lambda n: None)
        assert engine.fsm_state == FSMState.Complete

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    def test_fsm_empty_workflow(self):
        """Empty steps: [] → still transitions Pending → Running → Complete."""
        yaml_content = """
steps: []
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        engine.execute({}, lambda n: None)

        assert engine.fsm_state == FSMState.Complete
        assert engine.state_history == [
            FSMState.Pending, FSMState.Running, FSMState.Complete
        ]

    def test_fsm_state_alias(self):
        """state getter is alias for fsm_state."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        assert engine.state == engine.fsm_state

        engine.execute({}, lambda n: None)
        assert engine.state == engine.fsm_state
        assert engine.state == FSMState.Complete

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    def test_fsm_transitions_to_failed_on_error(self):
        """Executor throwing → FSM transitions to Failed."""
        yaml_content = """
steps:
  - process: crash
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        def executor(name):
            raise ValueError("intentional crash")

        with pytest.raises(ValueError):
            engine.execute({}, executor)

        assert engine.fsm_state == FSMState.Failed

    def test_fsm_history_includes_failed(self):
        """History records Failed state on error."""
        yaml_content = """
steps:
  - process: crash
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        with pytest.raises(ValueError):
            engine.execute({}, lambda n: (_ for _ in ()).throw(ValueError("boom")))

        history = engine.state_history
        assert FSMState.Failed in history
        assert history[-1] == FSMState.Failed
