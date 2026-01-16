"""
Test Flux DSL: flux: while
Tests the while loop functionality via Rust WorkflowEngine.
"""
import pytest


class TestFluxWhile:
    """Test Flux DSL while loop."""

    def test_while_basic_counter(self):
        """Test while loop with counter condition."""
        from theus_core import WorkflowEngine

        yaml_content = """
name: test_while
steps:
  - process: init_counter
  - flux: while
    condition: "counter < 3"
    do:
      - process: increment
  - process: finalize
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        # Mock context with counter
        ctx = {"counter": 0}
        executed = []

        def executor(name):
            nonlocal ctx
            executed.append(name)
            if name == "init_counter":
                ctx["counter"] = 0
            elif name == "increment":
                ctx["counter"] += 1

        result = engine.execute(ctx, executor)

        # Expected: init_counter, increment x3, finalize
        assert executed == [
            "init_counter",
            "increment",
            "increment",
            "increment",
            "finalize",
        ]

    def test_while_false_condition_skips(self):
        """Test while loop with initially false condition."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - process: before
  - flux: while
    condition: "False"
    do:
      - process: never_runs
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {}
        executed = []

        def executor(name):
            executed.append(name)

        engine.execute(ctx, executor)

        assert executed == ["before", "after"]

    def test_while_safety_trip(self):
        """Test that infinite loops are caught by safety limit."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - flux: while
    condition: "True"
    do:
      - process: loop_forever
"""
        engine = WorkflowEngine(yaml_content, 10, False)  # Low limit
        ctx = {}
        executed = []

        def executor(name):
            executed.append(name)

        with pytest.raises(RuntimeError, match="Safety Trip"):
            engine.execute(ctx, executor)

        # Should have hit the limit
        assert len(executed) <= 10
