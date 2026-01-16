import pytest
import yaml
from theus_core import WorkflowEngine
from theus.structures import State, FrozenDict

# TDD: V2 Compatibility (Linear Steps -> Graph)

def test_legacy_linear_workflow_parsing():
    """
    V2 YAML often used a simple 'steps' list.
    V3 expects a 'nodes' graph.
    The engine should auto-convert list to linked graph.
    """
    legacy_yaml = """
    name: LegacyFlow
    steps:
      - step_1
      - step_2
      - step_3
    """
    
    # This should NOT raise ValueError
    try:
        engine = WorkflowEngine(legacy_yaml)
    except ValueError as e:
        pytest.fail(f"Failed to load legacy YAML: {e}")
        
    # Verify Simulation
    # We need a dummy context because simulate evaluates conditions (though linear has none)
    # But simulate signature: simulate(py, ctx)
    # in Python: engine.simulate(ctx)
    
    state = State() # Empty state
    # We need a context object that behaves like dict or object for eval?
    # fsm.rs uses checking ctx.bind(py).
    # We can pass empty dict? Or ProcessContext?
    # fsm.rs signature: `fn simulate(&self, py: Python, ctx: Py<PyDict>)`
    # So we pass a dict.
    
    path = engine.simulate({})
    
    assert path == ["step_1", "step_2", "step_3"]

def test_legacy_mixed_structure():
    """
    V2 sometimes used explicit dictionaries in steps?
    If so, we assume 'process' key is the node name.
    steps:
      - process: step_1
      - process: step_2
    """
    complex_yaml = """
    name: ComplexLegacy
    steps:
      - process: step_A
      - process: step_B
    """
    
    engine = WorkflowEngine(complex_yaml)
    path = engine.simulate({})
    assert path == ["step_A", "step_B"]
