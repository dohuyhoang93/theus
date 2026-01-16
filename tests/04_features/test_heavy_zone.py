import pytest
from theus.structures import State

# TDD: Heavy Zone Ref Counting

def test_heavy_zone_no_copy():
    # Mock Tensor
    tensor_mock = [1] * 1000
    
    # In v3, State accepts 'heavy' dict directly. No 'Heavy' wrapper class needed here.
    # The 'heavy' dict values are stored in Arc<T> in Rust.
    state = State(heavy={"model": tensor_mock})
    
    # Update state (clone)
    # This creates a NEW State object, but heavy entries should share memory (Arc)
    state_v2 = state.update(data={"x": 1})
    
    # Heavy object address MUST be identical (Arc clone, not Deep Copy)
    assert id(state.heavy["model"]) == id(state_v2.heavy["model"])
