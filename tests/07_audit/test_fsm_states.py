"""
Test FSM States: WorkflowEngine state machine.
TDD - Tests written BEFORE implementation.

Per VISION.md:
- FSM quản lý trạng thái chờ đợi: WAITING_IO state
- Khi có kết quả (từ Outbox hoặc Callback), FSM chuyển sang PROCESSING

States: Pending -> Running -> WaitingIO -> Complete
"""
import pytest


class TestFSMStates:
    """Test WorkflowEngine FSM state machine."""

    def test_fsm_state_enum_exists(self):
        """FSMState enum should exist with correct variants."""
        from theus_core import FSMState
        
        assert hasattr(FSMState, 'Pending')
        assert hasattr(FSMState, 'Running')
        assert hasattr(FSMState, 'WaitingIO')
        assert hasattr(FSMState, 'Complete')
        assert hasattr(FSMState, 'Failed')

    def test_workflow_engine_has_state(self):
        """WorkflowEngine should expose current FSM state."""
        from theus_core import WorkflowEngine, FSMState
        
        yaml_content = """
steps:
  - process: step_a
"""
        engine = WorkflowEngine(yaml_content)
        
        # Initial state should be Pending
        assert engine.state == FSMState.Pending

    def test_state_transitions_to_running(self):
        """State should transition to Running when execute() is called."""
        from theus_core import WorkflowEngine, FSMState
        
        yaml_content = """
steps:
  - process: step_a
"""
        engine = WorkflowEngine(yaml_content)
        
        # Start execution
        ctx = {}
        executed = []
        
        def executor(name):
            executed.append(name)
            # Check state during execution
            assert engine.fsm_state == FSMState.Running
        
        engine.execute(ctx, executor)
        
        # After execution
        assert engine.fsm_state == FSMState.Complete

    def test_state_waiting_io_on_async_process(self):
        """State should transition to WaitingIO for async processes."""
        from theus_core import WorkflowEngine, FSMState
        import asyncio
        
        yaml_content = """
steps:
  - process: async_step
"""
        engine = WorkflowEngine(yaml_content)
        
        async_started = False
        
        async def async_executor(name):
            nonlocal async_started
            async_started = True
            # Check state during async wait
            assert engine.fsm_state == FSMState.WaitingIO
            await asyncio.sleep(0.1)
        
        # Execute async workflow
        async def main():
            await engine.execute_async({}, async_executor)

        asyncio.run(main())
        
        assert async_started
        assert engine.fsm_state == FSMState.Complete

    def test_state_failed_on_error(self):
        """State should transition to Failed on process error."""
        from theus_core import WorkflowEngine, FSMState
        
        yaml_content = """
steps:
  - process: failing_step
"""
        engine = WorkflowEngine(yaml_content)
        
        def failing_executor(name):
            raise RuntimeError("Process failed")
        
        with pytest.raises(RuntimeError):
            engine.execute({}, failing_executor)
        
        assert engine.fsm_state == FSMState.Failed

    def test_state_history(self):
        """Engine should track state transition history."""
        from theus_core import WorkflowEngine, FSMState
        
        yaml_content = """
steps:
  - process: step_a
  - process: step_b
"""
        engine = WorkflowEngine(yaml_content)
        
        def executor(name):
            pass
        
        engine.execute({}, executor)
        
        history = engine.state_history
        assert len(history) >= 3  # Pending -> Running -> Complete
        assert history[0] == FSMState.Pending
        assert FSMState.Running in history
        assert history[-1] == FSMState.Complete

    def test_state_observers(self):
        """External observers can subscribe to state changes."""
        from theus_core import WorkflowEngine, FSMState
        
        yaml_content = """
steps:
  - process: step_a
"""
        engine = WorkflowEngine(yaml_content)
        
        observed_states = []
        
        def on_state_change(old_state, new_state):
            observed_states.append((old_state, new_state))
        
        engine.add_state_observer(on_state_change)
        
        engine.execute({}, lambda name: None)
        
        assert len(observed_states) >= 2
        assert (FSMState.Pending, FSMState.Running) in observed_states
        assert (FSMState.Running, FSMState.Complete) in observed_states
