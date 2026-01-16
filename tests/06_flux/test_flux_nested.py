"""
Test Flux DSL: Nested structures
Tests complex nested while/if combinations via Rust WorkflowEngine.
"""
import pytest


class TestFluxNested:
    """Test Flux DSL nested control flow."""

    def test_if_inside_while(self):
        """Test if block nested inside while loop."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - flux: while
    condition: "i < 3"
    do:
      - flux: if
        condition: "i % 2 == 0"
        then:
          - process: even
        else:
          - process: odd
      - process: next
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"i": 0}
        executed = []

        def executor(name):
            nonlocal ctx
            executed.append(name)
            if name == "next":
                ctx["i"] += 1

        engine.execute(ctx, executor)

        # i=0 (even), i=1 (odd), i=2 (even)
        assert executed == [
            "even",
            "next",
            "odd",
            "next",
            "even",
            "next",
        ]

    def test_while_inside_if(self):
        """Test while loop nested inside if block."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - flux: if
    condition: "enable_loop"
    then:
      - flux: while
        condition: "count < 2"
        do:
          - process: loop_step
    else:
      - process: skip_loop
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        # Test with loop enabled
        ctx = {"enable_loop": True, "count": 0}
        executed = []

        def executor(name):
            nonlocal ctx
            executed.append(name)
            if name == "loop_step":
                ctx["count"] += 1

        engine.execute(ctx, executor)
        assert executed == ["loop_step", "loop_step"]

        # Test with loop disabled
        ctx = {"enable_loop": False, "count": 0}
        executed = []
        engine.execute(ctx, executor)
        assert executed == ["skip_loop"]

    def test_deeply_nested(self):
        """Test deeply nested structures (3 levels)."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - flux: if
    condition: "level1"
    then:
      - flux: while
        condition: "level2_count < 1"
        do:
          - flux: if
            condition: "level3"
            then:
              - process: deep_process
          - process: increment
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"level1": True, "level2_count": 0, "level3": True}
        executed = []

        def executor(name):
            nonlocal ctx
            executed.append(name)
            if name == "increment":
                ctx["level2_count"] += 1

        engine.execute(ctx, executor)
        assert executed == ["deep_process", "increment"]

    def test_flux_run_block(self):
        """Test flux: run nested steps block."""
        from theus_core import WorkflowEngine

        yaml_content = """
steps:
  - process: start
  - flux: run
    steps:
      - process: nested_a
      - process: nested_b
  - process: end
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {}
        executed = []

        def executor(name):
            executed.append(name)

        engine.execute(ctx, executor)
        assert executed == ["start", "nested_a", "nested_b", "end"]
