import pytest
import asyncio
from theus.engine import TheusEngine
from theus.structures import StateUpdate

# TDD: Verify CAS (Compare-And-Swap) checks prevents Data Races

@pytest.mark.asyncio
async def test_cas_detects_conflict():
    engine = TheusEngine()
    # Initial: x=0 version=1
    
    # Process A reads version=1. Calculates x=1. Sleep 100ms.
    # Process B reads version=1. Calculates x=2. Commit IMMEDIATELY.
    # Process A wakes up. Tries to commit x=1 with base_version=1.
    # ENGINE MUST REJECT Process A because current version is 2.
    
    async def slow_process(ctx):
        v_start = ctx.version
        await asyncio.sleep(0.1)
        return StateUpdate(key="x", val=1, assert_version=v_start)

    async def fast_process(ctx):
        v_start = ctx.version
        return StateUpdate(key="x", val=2, assert_version=v_start)

    # Launch both
    t1 = asyncio.create_task(engine.execute(slow_process))
    t2 = asyncio.create_task(engine.execute(fast_process))
    
    # B succeeds
    await t2
    
    # A fails
    with pytest.raises(Exception, match="CAS Version Mismatch"):
        await t1

@pytest.mark.asyncio
async def test_cas_stress_increment():
    # 100 tasks incrementing x. Logic MUST use CAS retry loop handled by Engine or User.
    # If naive, final result < 100. If safe, final result == 100.
    # Here we test that Engine correctly serializes commits or rejects stale ones.
    pass
