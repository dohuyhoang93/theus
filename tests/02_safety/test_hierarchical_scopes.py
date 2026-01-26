import pytest
from theus.contracts import process
from theus.engine import TheusEngine

# TDD: Output Scopes

from theus.structures import StateUpdate

@process(inputs=[], outputs=["domain.user.*"])
async def malicious_process(ctx):
    # Try to write outside scope using v3 StateUpdate
    return StateUpdate(key="domain.system.config", val="hacked")

@pytest.mark.asyncio
async def test_scope_enforcement():
    engine = TheusEngine()
    engine.register(malicious_process)
    
    with pytest.raises(Exception, match="permission"):
        await engine.execute("malicious_process")
