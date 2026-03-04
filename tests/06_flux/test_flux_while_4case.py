"""
Test Flux DSL: flux: while — 4-Case Coverage
Covers: Standard, Related, Boundary, Conflict
"""

import pytest
from theus_core import WorkflowEngine


class TestFluxWhile4Case:
    """4-Case test coverage for Flux while loop."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    def test_while_multiple_processes_in_body(self):
        """Multiple processes in do: block per iteration."""
        yaml_content = """
steps:
  - flux: while
    condition: "i < 2"
    do:
      - process: step_a
      - process: step_b
      - process: advance
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"i": 0}
        executed = []

        def executor(name):
            executed.append(name)
            if name == "advance":
                ctx["i"] += 1

        engine.execute(ctx, executor)
        assert executed == [
            "step_a", "step_b", "advance",
            "step_a", "step_b", "advance",
        ]

    def test_while_with_modulo_condition(self):
        """Condition uses modulo operator."""
        yaml_content = """
steps:
  - flux: while
    condition: "counter % 5 != 0 or counter == 0"
    do:
      - process: tick
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"counter": 0}
        executed = []

        def executor(name):
            ctx["counter"] += 1
            executed.append(name)

        engine.execute(ctx, executor)
        # counter starts 0 → condition True (counter==0), tick → counter=1
        # counter=1 → 1%5!=0 → True, tick → counter=2
        # ...
        # counter=4 → 4%5!=0 → True, tick → counter=5
        # counter=5 → 5%5==0 and counter!=0 → False → stop
        assert len(executed) == 5

    # ================================================================
    # RELATED (Liên quan)
    # ================================================================

    def test_while_interacts_with_signal_dict(self):
        """Signal dict mutation controls loop termination."""
        yaml_content = """
steps:
  - flux: while
    condition: "signals.get('running') == True"
    do:
      - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        signals = {"running": True}
        ctx = {"signals": signals}
        executed = []
        call_count = 0

        def executor(name):
            nonlocal call_count
            executed.append(name)
            call_count += 1
            if call_count >= 3:
                signals["running"] = False

        engine.execute(ctx, executor)
        assert len(executed) == 3

    def test_while_respects_max_ops_across_nesting(self):
        """Safety trip counts ops across nested while + if."""
        yaml_content = """
steps:
  - flux: while
    condition: "True"
    do:
      - flux: if
        condition: "True"
        then:
          - process: inner
"""
        # NOTE: Each iteration = 1 (while check) + 1 (if check) + 1 (process) = 3 ops
        engine = WorkflowEngine(yaml_content, 10, False)
        executed = []

        with pytest.raises(RuntimeError, match="Safety Trip"):
            engine.execute({}, lambda n: executed.append(n))

        assert len(executed) <= 10

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    def test_while_zero_iterations(self):
        """Condition false immediately — body never executes."""
        yaml_content = """
steps:
  - process: before
  - flux: while
    condition: "count > 100"
    do:
      - process: never_runs
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({"count": 0}, lambda n: executed.append(n))
        assert executed == ["before", "after"]

    def test_while_exactly_one_iteration(self):
        """Loop body executes exactly once."""
        yaml_content = """
steps:
  - flux: while
    condition: "n < 1"
    do:
      - process: once
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"n": 0}
        executed = []

        def executor(name):
            executed.append(name)
            ctx["n"] += 1

        engine.execute(ctx, executor)
        assert executed == ["once"]

    def test_while_max_ops_equals_1(self):
        """max_ops=1 triggers safety trip on first while body op."""
        yaml_content = """
steps:
  - flux: while
    condition: "True"
    do:
      - process: loop_body
"""
        engine = WorkflowEngine(yaml_content, 1, False)
        with pytest.raises(RuntimeError, match="Safety Trip"):
            engine.execute({}, lambda n: None)

    def test_while_empty_do_block(self):
        """Empty do: block with always-true condition → safety trip catches it."""
        yaml_content = """
steps:
  - flux: while
    condition: "True"
    do: []
"""
        engine = WorkflowEngine(yaml_content, 10, False)
        # NOTE: Phương án A ensures ops_counter increments per while iteration,
        # so empty do block no longer causes true infinite loop.
        with pytest.raises(RuntimeError, match="Safety Trip"):
            engine.execute({}, lambda n: None)

    def test_while_condition_type_coercion(self):
        """Condition evaluates to falsy non-boolean (empty string)."""
        yaml_content = """
steps:
  - flux: while
    condition: "val"
    do:
      - process: runs
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        # Empty string is falsy
        executed = []
        engine.execute({"val": ""}, lambda n: executed.append(n))
        assert executed == []

        # Non-empty string is truthy (need to stop it)
        ctx = {"val": "yes"}
        executed = []

        def executor(name):
            executed.append(name)
            ctx["val"] = ""  # Make falsy after first iteration

        engine.execute(ctx, executor)
        assert executed == ["runs"]

    def test_while_large_iteration_count(self):
        """100 iterations without safety trip (max_ops high enough)."""
        yaml_content = """
steps:
  - flux: while
    condition: "n < 100"
    do:
      - process: tick
"""
        engine = WorkflowEngine(yaml_content, 50000, False)
        ctx = {"n": 0}

        def executor(name):
            ctx["n"] += 1

        result = engine.execute(ctx, executor)
        assert ctx["n"] == 100
        assert len(result) == 100

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    def test_while_condition_error_mid_loop(self):
        """Variable deleted mid-loop → NameError on re-evaluation."""
        yaml_content = """
steps:
  - flux: while
    condition: "counter < 5"
    do:
      - process: step
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"counter": 0}

        def executor(name):
            ctx["counter"] += 1
            if ctx["counter"] >= 2:
                # NOTE: Remove the variable the condition depends on
                del ctx["counter"]

        with pytest.raises(Exception):
            engine.execute(ctx, executor)

    def test_while_executor_raises_mid_loop(self):
        """Executor throws at iteration N → loop stops, error propagates."""
        yaml_content = """
steps:
  - flux: while
    condition: "i < 10"
    do:
      - process: work
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        ctx = {"i": 0}
        executed = []

        def executor(name):
            ctx["i"] += 1
            executed.append(name)
            if ctx["i"] == 3:
                raise RuntimeError("Crash at iteration 3")

        with pytest.raises(RuntimeError, match="Crash at iteration 3"):
            engine.execute(ctx, executor)

        assert len(executed) == 3
