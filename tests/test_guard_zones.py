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
