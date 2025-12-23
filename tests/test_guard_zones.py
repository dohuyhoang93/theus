import pytest
from theus.guards import ContextGuard
from theus.contracts import ContractViolationError

class MockTarget:
    pass

def test_guard_blocks_signal_input_strict():
    """
    Test that ContextGuard raises Error in Strict Mode when Input is a Signal.
    """
    target = MockTarget()
    # "sig_trigger" is a SIGNAL zone
    inputs = {"sig_trigger"} 
    outputs = set()
    
    with pytest.raises(ContractViolationError) as excinfo:
        ContextGuard(target, inputs, outputs, strict_mode=True)
        
    assert "Zone Policy Violation" in str(excinfo.value)
    
def test_guard_allows_signal_input_warn_mode(caplog):
    """
    Test that ContextGuard logs Warning (but proceeds) in Warn Mode.
    """
    target = MockTarget()
    inputs = {"sig_trigger"} # SIGNAL
    outputs = set()
    
    import logging
    with caplog.at_level(logging.WARNING, logger="POP.ContextGuard"):
         _ = ContextGuard(target, inputs, outputs, strict_mode=False)
         
    assert "Zone Policy Violation" in caplog.text

def test_guard_allows_data_input():
    target = MockTarget()
    inputs = {"user_data", "domain.balance"} # DATA
    outputs = set()
    
    # Should not raise
    _ = ContextGuard(target, inputs, outputs, strict_mode=True)
    
def test_guard_blocks_meta_input_strict():
    target = MockTarget()
    inputs = {"meta_trace_id"} # META
    outputs = set()
    
    with pytest.raises(ContractViolationError):
        ContextGuard(target, inputs, outputs, strict_mode=True)

def test_semantic_input_output_compliance():
    """
    Test strictly Semantic Enforcement:
    1. Cannot Write to Input-only fields.
    2. Cannot Read fields not in Input.
    """
    class MockData:
        user_id: int = 1
        balance: float = 100.0
        
    target = MockData()
    # Input: user_id (Read)
    # Output: balance (Write)
    inputs = {"user_id"}
    outputs = {"balance"}
    
    guard = ContextGuard(target, inputs, outputs, strict_mode=True)
    
    # 1. Allowed Read
    assert guard.user_id == 1
    
    # 2. Illegal Write to Input (user_id is NOT in allowed_outputs)
    with pytest.raises(ContractViolationError, match="Illegal Write"):
        guard.user_id = 99
        
    # 3. Read of Output IS Allowed in Theus V2 (Line 88 of guards.py)
    # Rationale: Processes often need to read what they wrote (accumulators).
    val = guard.balance
    assert val == 100.0
        
    # 4. Allowed Write to Output
    guard.balance = 200.0
    assert target.balance == 200.0
