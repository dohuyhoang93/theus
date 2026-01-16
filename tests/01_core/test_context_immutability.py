import pytest
from theus.contracts import process
from theus.engine import TheusEngine
from theus.structures import State, ContextError

# TDD: v3 Context is Immutable
# Direct assignment `ctx.x = 1` MUST FAIL
# `ctx.update()` MUST RETURN NEW STATE

def test_context_direct_mutation_fails():
    state = State(data={"x": 0})
    
    with pytest.raises(ContextError, match="Immutable"):
        state.x = 1
        
    with pytest.raises(ContextError, match="Immutable"):
        state.data["x"] = 1

def test_context_update_returns_new_ref():
    state_v1 = State(data={"x": 0})
    state_v2 = state_v1.update(data={"x": 1})
    
    assert state_v1.data["x"] == 0
    assert state_v2.data["x"] == 1
    assert id(state_v1) != id(state_v2) # Zero-copy implies structural sharing, but distinct root objects

def test_context_deep_structure_sharing():
    # Verify that untouched branches effectively share memory (mock check via id, though Rust impl handles deep sharing)
    data = {"a": {"val": 1}, "b": {"val": 2}}
    state_v1 = State(data=data)
    
    state_v2 = state_v1.update(data={"a": {"val": 99}})
    
    # "b" was not touched, structurally it might be shared
    # In Python wrapper we check functional correctness
    assert state_v2.data["a"]["val"] == 99
    assert state_v2.data["b"]["val"] == 2
    assert state_v1.data["a"]["val"] == 1
