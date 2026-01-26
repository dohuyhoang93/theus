import pytest
import asyncio
from theus.engine import TheusEngine

# TDD: Consistent Reads (Snapshot Isolation)

@pytest.mark.asyncio
async def test_reader_isolation():
    engine = TheusEngine()
    # Correct Way to Init State in v3 (Immutable)
    # We must construct a new state and commit it (or use internal API if needed for setup)
    # For setup, we can use compare_and_swap from version 1
    engine.compare_and_swap(1, {"x": 0}, None, None)
    
    async def long_reader(ctx):
        # Finds x=0
        val1 = ctx.data["x"]
        await asyncio.sleep(0.2)
        # Even if writer changed it globally, THIS context must see snapshot x=0
        val2 = ctx.data["x"]
        return val1, val2

    async def fast_writer(ctx):
        await asyncio.sleep(0.05)
        return {"x": 99}

    task_read = asyncio.create_task(engine.execute(long_reader))
    task_write = asyncio.create_task(engine.execute(fast_writer))
    
    await task_write # Global state is now 99
    
    v1, v2 = await task_read
    
    assert v1 == 0
    assert v2 == 0 # Crucial: Must not see '99' appearing mid-process!
