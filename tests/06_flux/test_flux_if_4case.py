"""
Test Flux DSL: flux: if — 4-Case Coverage
Covers: Standard, Related, Boundary, Conflict
"""

import pytest
from theus_core import WorkflowEngine


class TestFluxIf4Case:
    """4-Case test coverage for Flux if/else branching."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    def test_if_elif_chain(self):
        """Simulate elif via nested if/else."""
        yaml_content = """
steps:
  - flux: if
    condition: "x > 10"
    then:
      - process: big
    else:
      - flux: if
        condition: "x > 5"
        then:
          - process: medium
        else:
          - process: small
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        # x=15 → big
        ctx = {"x": 15}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["big"]

        # x=7 → medium
        ctx = {"x": 7}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["medium"]

        # x=2 → small
        ctx = {"x": 2}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["small"]

    def test_if_with_dict_access(self):
        """Condition accessing dict keys via bracket notation."""
        yaml_content = """
steps:
  - flux: if
    condition: "domain['score'] > 50"
    then:
      - process: pass_exam
    else:
      - process: fail_exam
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        ctx = {"domain": {"score": 80}}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["pass_exam"]

        ctx = {"domain": {"score": 30}}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["fail_exam"]

    # ================================================================
    # RELATED (Liên quan)
    # ================================================================

    def test_if_condition_uses_len_builtin(self):
        """Condition uses len() from restricted builtins."""
        yaml_content = """
steps:
  - flux: if
    condition: "len(items) > 0"
    then:
      - process: process_items
    else:
      - process: no_items
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        ctx = {"items": [1, 2, 3]}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["process_items"]

        ctx = {"items": []}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["no_items"]

    def test_if_condition_uses_min_max(self):
        """Condition uses min/max from restricted builtins."""
        yaml_content = """
steps:
  - flux: if
    condition: "max(scores) > 90"
    then:
      - process: top_performer
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        ctx = {"scores": [45, 92, 78]}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["top_performer"]

        ctx = {"scores": [45, 50, 78]}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == []

    def test_if_with_nested_dict_context(self):
        """Condition accesses deeply nested dict."""
        yaml_content = """
steps:
  - flux: if
    condition: "cfg['db']['host'] == 'localhost'"
    then:
      - process: use_local_db
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        ctx = {"cfg": {"db": {"host": "localhost", "port": 5432}}}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["use_local_db"]

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    def test_if_empty_then_block(self):
        """Empty then block — should not crash, just skip."""
        yaml_content = """
steps:
  - process: before
  - flux: if
    condition: "True"
    then: []
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == ["before", "after"]

    def test_if_condition_always_true(self):
        """Literal True condition."""
        yaml_content = """
steps:
  - flux: if
    condition: "True"
    then:
      - process: always_runs
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == ["always_runs"]

    def test_if_condition_always_false(self):
        """Literal False condition."""
        yaml_content = """
steps:
  - flux: if
    condition: "False"
    then:
      - process: never_runs
    else:
      - process: always_else
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == ["always_else"]

    def test_if_condition_with_none_comparison(self):
        """Condition comparing to None."""
        yaml_content = """
steps:
  - flux: if
    condition: "val is None"
    then:
      - process: handle_none
    else:
      - process: handle_value
"""
        engine = WorkflowEngine(yaml_content, 100, False)

        ctx = {"val": None}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["handle_none"]

        ctx = {"val": 42}
        executed = []
        engine.execute(ctx, lambda n: executed.append(n))
        assert executed == ["handle_value"]

    def test_if_missing_variable_in_condition(self):
        """Condition references undefined variable → NameError."""
        yaml_content = """
steps:
  - flux: if
    condition: "undefined_var > 0"
    then:
      - process: should_not_run
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        with pytest.raises(Exception):
            engine.execute({}, lambda n: None)

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    def test_if_condition_syntax_error(self):
        """Malformed condition expression → SyntaxError."""
        yaml_content = """
steps:
  - flux: if
    condition: "x >>"
    then:
      - process: never
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        with pytest.raises(Exception):
            engine.execute({"x": 1}, lambda n: None)

    def test_if_condition_calls_forbidden_builtin(self):
        """Condition attempts __import__ — should be blocked by restricted builtins."""
        yaml_content = """
steps:
  - flux: if
    condition: "__import__('os').system('echo hacked') == 0"
    then:
      - process: hacked
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        with pytest.raises(Exception):
            engine.execute({}, lambda n: None)

    def test_if_executor_raises_in_then(self):
        """Executor throws exception inside then branch."""
        yaml_content = """
steps:
  - process: before
  - flux: if
    condition: "True"
    then:
      - process: will_crash
  - process: after
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []

        def executor(name):
            executed.append(name)
            if name == "will_crash":
                raise ValueError("Intentional crash")

        with pytest.raises(ValueError, match="Intentional crash"):
            engine.execute({}, executor)

        # NOTE: "before" should have executed, "after" should NOT
        assert "before" in executed
        assert "after" not in executed
