import pytest
from theus.engine import TheusEngine
from theus.structures import State

# TDD: Rollback works by discarding the 'future' reference, not by undoing writes.

def test_transaction_rollback_is_instant():
    engine = TheusEngine()
    initial_state = engine.state
    
    try:
        with engine.transaction() as tx:
            tx.update({"x": 999})
            raise ValueError("Abort!")
    except ValueError:
        pass
        
    # State should be EXACTLY the initial object (reference equality)
    assert engine.state is initial_state
    assert engine.state.data.get("x") != 999

def test_transaction_commit_advances_pointer():
    engine = TheusEngine()
    initial_state = engine.state
    
    with engine.transaction() as tx:
        tx.update({"x": 999})
        # Auto-commit on exit
        
    assert engine.state is not initial_state
    assert engine.state.data["x"] == 999
