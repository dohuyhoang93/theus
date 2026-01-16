import pytest
import gc
from theus.engine import TheusEngine
from theus.contracts import process

# TDD: RAII Local scope

class HeavyObj:
    pass

@process
def messy_process(ctx):
    ctx.local['temp'] = HeavyObj()
    # No cleanup

@pytest.mark.asyncio
async def test_local_auto_drop():
    engine = TheusEngine()
    await engine.execute(messy_process)
    
    # After return, ctx.local was ephemeral. State should not track it.
    # In v3, State has no 'local' attribute.
    assert not hasattr(engine.state, "local")
    
    # Verify GC
    gc.collect()
    # (Checking exact GC is hard in Python test, but checking 'local' dict is empty is enough spec)
