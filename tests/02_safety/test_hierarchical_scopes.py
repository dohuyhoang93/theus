import pytest
from theus.contracts import process
from theus.engine import TheusEngine

# TDD: Output Scopes

from theus.structures import StateUpdate


@process(inputs=[], outputs=["domain.user.*"])
async def malicious_process(ctx):
    # Try to write outside scope using ctx mutation
    # If the guard works, this should raise a PermissionError
    ctx.domain.system = "hacked"
    return "done"


@pytest.mark.asyncio
async def test_scope_enforcement():
    engine = TheusEngine()
    engine.register(malicious_process)

    with pytest.raises(Exception):
        await engine.execute("malicious_process")
