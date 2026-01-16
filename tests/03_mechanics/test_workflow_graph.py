import pytest
from theus.workflow import WorkflowEngine

# TDD: Graph execution

def test_workflow_conditional_branching():
    # A -> (x>5) -> B
    #   -> (x<=5) -> C
    
    yaml_config = """
    nodes:
      start: A
      A: 
        next: 
          if "x > 5": B
          else: C
      B: {}
      C: {}
    """
    
    wf = WorkflowEngine(yaml_config)
    
    # Case 1
    path1 = wf.simulate({"x": 10})
    assert path1 == ["A", "B"]
    
    # Case 2
    path2 = wf.simulate({"x": 1})
    assert path2 == ["A", "C"]
