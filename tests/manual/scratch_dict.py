"""Verify __dict__ proxying: should return empty dict (no data exposed)."""
import asyncio
from theus.engine import TheusEngine
from theus.contracts import process
from theus.context import BaseDomainContext

class MyDomain(BaseDomainContext):
    const_config: dict = {}
    status: str = ""

@process(inputs=["domain"], outputs=["domain.status"])
async def p_mutate_dict(ctx):
    print(f"type(ctx) = {type(ctx)}")
    print(f"type(ctx.domain) = {type(ctx.domain)}")
    
    try:
        d = ctx.domain.__dict__
        print(f"type(d) = {type(d)}")
        print(f"d keys = {list(d.keys()) if isinstance(d, dict) else 'N/A'}")
    except PermissionError as e:
        print(f"BLOCKED __dict__ access: {e}")
        ctx.domain.status = 'PASS'
        return None
    
    # If we get here, __dict__ returned something
    # With empty-dict approach: d should be empty
    if len(d) == 0:
        print("__dict__ returned empty dict — data not exposed")
        ctx.domain.status = 'PASS'
        return None
    
    # If dict has data, try to mutate
    try:
        d['const_config'] = {'hacked': True}
        ctx.domain.status = 'FAIL_CONST_WRITTEN'
    except PermissionError as e:
        print(f"BLOCKED write: {e}")
        ctx.domain.status = 'PASS'
    return None

async def main():
    engine = TheusEngine(context={'domain': {'const_config': {'original': True}, 'status': ''}})
    await engine.execute(p_mutate_dict)
    status = engine.state.data['domain'].get('status')
    print(f'status: {status}')
    assert status == 'PASS', f"Expected PASS, got {status}"
    print("__DICT__ PROXYING TEST PASSED")

asyncio.run(main())
