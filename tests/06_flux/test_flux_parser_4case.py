"""
Test Flux DSL: YAML Parser — 4-Case Coverage
Covers: Standard, Boundary, Conflict
"""

import pytest
from theus_core import WorkflowEngine


class TestFluxParser4Case:
    """4-Case test coverage for Flux YAML parser."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    def test_parse_simple_process(self):
        """Standard process step parses correctly."""
        yaml_content = """
steps:
  - process: my_process
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == ["my_process"]

    def test_parse_string_shorthand(self):
        """Bare string shorthand: `- name` instead of `- process: name`."""
        yaml_content = """
steps:
  - my_shorthand
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == ["my_shorthand"]

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    def test_parse_invalid_yaml(self):
        """Completely invalid YAML syntax → PyValueError."""
        with pytest.raises(ValueError, match="Invalid YAML"):
            WorkflowEngine("{{{{ not valid yaml ]]]]", 100, False)

    def test_parse_missing_condition_in_while(self):
        """flux: while without condition field → parse error."""
        yaml_content = """
steps:
  - flux: while
    do:
      - process: loop
"""
        with pytest.raises(ValueError, match="condition"):
            WorkflowEngine(yaml_content, 100, False)

    def test_parse_missing_do_in_while(self):
        """flux: while without do block → parse error."""
        yaml_content = """
steps:
  - flux: while
    condition: "True"
"""
        with pytest.raises(ValueError, match="do"):
            WorkflowEngine(yaml_content, 100, False)

    def test_parse_missing_condition_in_if(self):
        """flux: if without condition → parse error."""
        yaml_content = """
steps:
  - flux: if
    then:
      - process: branch
"""
        with pytest.raises(ValueError, match="condition"):
            WorkflowEngine(yaml_content, 100, False)

    def test_parse_missing_steps_in_run(self):
        """flux: run without steps block → parse error."""
        yaml_content = """
steps:
  - flux: run
"""
        with pytest.raises(ValueError, match="steps"):
            WorkflowEngine(yaml_content, 100, False)

    def test_parse_unknown_flux_type(self):
        """Unknown flux type (e.g., foreach) → error."""
        yaml_content = """
steps:
  - flux: foreach
    items: "[1,2,3]"
"""
        with pytest.raises(ValueError, match="Unknown flux type"):
            WorkflowEngine(yaml_content, 100, False)

    def test_parse_empty_steps(self):
        """steps: [] (empty list) → valid empty workflow."""
        yaml_content = """
steps: []
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == []

    def test_parse_no_steps_key(self):
        """YAML without 'steps' key → valid but empty workflow."""
        yaml_content = """
name: no_steps_workflow
version: 1.0
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == []

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    def test_parse_if_without_then_block(self):
        """flux: if with condition but no then/else → valid, empty branches."""
        yaml_content = """
steps:
  - flux: if
    condition: "True"
"""
        # NOTE: Parser allows this — then_steps and else_steps default to empty
        engine = WorkflowEngine(yaml_content, 100, False)
        executed = []
        engine.execute({}, lambda n: executed.append(n))
        assert executed == []
