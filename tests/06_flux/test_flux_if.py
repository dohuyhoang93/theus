"""
Test Flux DSL: flux: if
Tests the conditional branching functionality via Rust WorkflowEngine.
"""
import pytest


class TestFluxIf:
    """Test Flux DSL if/else branching."""

    def test_if_true_branch(self):
        """Test if block executes then branch when true."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - process: before
  - flux: if
    condition: "flag == True"
    then:
      - process: then_branch
    else:
      - process: else_branch
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"flag": True}
        executed = []

        def executor(name):
            executed.append(name)

        engine.execute(ctx, executor)

        assert executed == ["before", "then_branch", "after"]

    def test_if_false_branch(self):
        """Test if block executes else branch when false."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - process: before
  - flux: if
    condition: "flag == True"
    then:
      - process: then_branch
    else:
      - process: else_branch
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"flag": False}
        executed = []

        def executor(name):
            executed.append(name)

        engine.execute(ctx, executor)

        assert executed == ["before", "else_branch", "after"]

    def test_if_no_else(self):
        """Test if block with no else clause."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - process: before
  - flux: if
    condition: "x > 5"
    then:
      - process: do_something
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        # Test when condition is true
        ctx = {"x": 10}
        executed = []

        def executor(name):
            executed.append(name)

        engine.execute(ctx, executor)
        assert executed == ["before", "do_something", "after"]

        # Test when condition is false (no else = skip)
        ctx = {"x": 3}
        executed = []
        engine.execute(ctx, executor)
        assert executed == ["before", "after"]

    def test_if_complex_condition(self):
        """Test if with complex expression."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - flux: if
    condition: "len(items) > 0 and count < max_count"
    then:
      - process: process_items
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"items": [1, 2, 3], "count": 5, "max_count": 10}
        executed = []

        def executor(name):
            executed.append(name)

        engine.execute(ctx, executor)
        assert executed == ["process_items"]
