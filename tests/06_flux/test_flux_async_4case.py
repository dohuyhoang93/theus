"""
Test Flux DSL: WorkflowEngine.execute_async — 4-Case Coverage
Tests the Rust execute_async method directly (not through TheusEngine wrapper).

NOTE: execute_async creates a coroutine by wrapping execute() in asyncio.to_thread.
When an executor callback returns a coroutine, the Rust engine uses
run_coroutine_threadsafe to schedule it on the main loop, transitioning FSM to WaitingIO.
"""

import asyncio
import pytest
from theus_core import WorkflowEngine, FSMState


class TestFluxAsync4Case:
    """4-Case test coverage for WorkflowEngine.execute_async."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    @pytest.mark.asyncio
    async def test_execute_async_basic(self):
        """execute_async returns awaitable coroutine, produces correct result."""
        yaml_content = """
steps:
  - process: step_a
  - process: step_b
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []

        def executor(name):
            executed.append(name)

        result = await engine.execute_async({}, executor)
        assert result == ["step_a", "step_b"]
        assert executed == ["step_a", "step_b"]

    @pytest.mark.asyncio
    async def test_execute_async_with_sync_process(self):
        """Sync executor works fine through execute_async path."""
        yaml_content = """
steps:
  - process: increment
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        state = {"count": 0}

        def executor(name):
            state["count"] += 1

        await engine.execute_async(state, executor)
        assert state["count"] == 1
        assert engine.fsm_state == FSMState.Complete

    # ================================================================
    # RELATED (Liên quan)
    # ================================================================

    @pytest.mark.asyncio
    async def test_execute_async_fsm_complete(self):
        """FSM transitions correctly: Pending → Running → Complete."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        assert engine.fsm_state == FSMState.Pending

        await engine.execute_async({}, lambda n: None)

        assert engine.fsm_state == FSMState.Complete
        history = engine.state_history
        assert history == [FSMState.Pending, FSMState.Running, FSMState.Complete]

    @pytest.mark.asyncio
    async def test_execute_async_observer_fires(self):
        """Observers are called during async execution."""
        yaml_content = """
steps:
  - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        transitions = []
        engine.add_state_observer(lambda old, new: transitions.append((old, new)))

        await engine.execute_async({}, lambda n: None)

        assert len(transitions) == 2
        assert transitions[0] == (FSMState.Pending, FSMState.Running)
        assert transitions[1] == (FSMState.Running, FSMState.Complete)

    @pytest.mark.asyncio
    async def test_execute_async_with_control_flow(self):
        """execute_async handles if/while control flow correctly.

        NOTE: execute_async shallow-copies ctx. Top-level key mutations from
        executor won't reflect in condition eval. Use nested dict so the inner
        object survives the shallow copy via shared reference.
        """
        yaml_content = """
steps:
  - flux: while
    condition: "state['i'] < 3"
    do:
      - process: loop_body
  - flux: if
    condition: "state['i'] == 3"
    then:
      - process: done
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        # NOTE: Nested dict survives ctx.copy() shallow copy
        state = {"i": 0}
        ctx = {"state": state}
        executed = []

        def executor(name):
            executed.append(name)
            if name == "loop_body":
                state["i"] += 1

        result = await engine.execute_async(ctx, executor)
        assert executed == ["loop_body", "loop_body", "loop_body", "done"]
        assert engine.fsm_state == FSMState.Complete

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    @pytest.mark.asyncio
    async def test_execute_async_empty_workflow(self):
        """Empty workflow through execute_async path."""
        yaml_content = """
steps: []
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        result = await engine.execute_async({}, lambda n: None)
        assert result == []
        assert engine.fsm_state == FSMState.Complete

    @pytest.mark.asyncio
    async def test_execute_async_safety_trip(self):
        """Safety trip fires through execute_async path."""
        yaml_content = """
steps:
  - flux: while
    condition: "True"
    do:
      - process: infinite
"""
        engine = WorkflowEngine(yaml_content, 5, False)

        with pytest.raises(RuntimeError, match="Safety Trip"):
            await engine.execute_async({}, lambda n: None)

        assert engine.fsm_state == FSMState.Failed

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    @pytest.mark.asyncio
    async def test_execute_async_executor_error(self):
        """Executor crash propagates through async path, FSM → Failed."""
        yaml_content = """
steps:
  - process: crash
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        def executor(name):
            raise ValueError("async executor crash")

        with pytest.raises(ValueError, match="async executor crash"):
            await engine.execute_async({}, executor)

        assert engine.fsm_state == FSMState.Failed

    @pytest.mark.asyncio
    async def test_execute_async_concurrent_workflows(self):
        """Two separate WorkflowEngines run concurrently via asyncio.gather."""
        yaml_a = """
steps:
  - process: task_a
"""
        yaml_b = """
steps:
  - process: task_b
"""
        engine_a = WorkflowEngine(yaml_a, 100, False)
        engine_b = WorkflowEngine(yaml_b, 100, False)

        results_a = []
        results_b = []

        async def run_a():
            return await engine_a.execute_async(
                {}, lambda n: results_a.append(n)
            )

        async def run_b():
            return await engine_b.execute_async(
                {}, lambda n: results_b.append(n)
            )

        await asyncio.gather(run_a(), run_b())

        assert results_a == ["task_a"]
        assert results_b == ["task_b"]
        assert engine_a.fsm_state == FSMState.Complete
        assert engine_b.fsm_state == FSMState.Complete
