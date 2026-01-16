import pytest
from theus.contracts import process, SemanticType, ContractViolationError
from theus.engine import TheusEngine

# TDD: Pure processes cannot see Signal/Meta

@process(inputs=["signal.stop"], semantic=SemanticType.PURE)
def invalid_pure_input(ctx):
    pass

@process(inputs=["data.x"], semantic=SemanticType.PURE)
def invalid_pure_access(ctx):
    # Try to reach hidden zone
    return ctx.signal.stop

def test_pure_function_cannot_declare_signal_input():
    engine = TheusEngine()
    # Contract validation happens at Registration or Execution time
    with pytest.raises(ContractViolationError, match="Pure process cannot take inputs from Zone: Signal"):
        engine.register(invalid_pure_input)

@pytest.mark.asyncio
async def test_pure_function_runtime_blindness():
    engine = TheusEngine()
    engine.register(invalid_pure_access)
    
    # Even if declared inputs are OK, runtime access to ctx.signal should fail
    # We await execution
    with pytest.raises(AttributeError, match="has no attribute 'signal'"):
        await engine.execute("invalid_pure_access")
