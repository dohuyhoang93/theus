import asyncio
from theus.engine import TheusEngine
from theus.contracts import process, AdminTransaction
from typing import Annotated
from theus.context import Mutable, BaseSystemContext, BaseDomainContext

class OverrideDomain(BaseDomainContext):
    log_events: Annotated[list, Mutable]
    const_data: Annotated[dict, Mutable]

class OverrideSystem(BaseSystemContext):
    domain: OverrideDomain

@process(outputs=["domain.const_config", "domain.internal_data", "domain.test_status"])
async def p_try_write_zones(ctx):
    # const_ cannot be written even with admin
    try:
        ctx.domain.const_config = {"new": "val"}
        ctx.domain.test_status = "ERROR_CONST_WRITTEN"
        return None
    except PermissionError:
        pass

    try:
        ctx.domain.const_config.append(1)
        ctx.domain.test_status = "ERROR_CONST_APPENDED"
        return None
    except PermissionError:
        pass
        
    try:
        ctx.domain.const_config.clear()
        ctx.domain.test_status = "ERROR_CONST_CLEARED"
        return None
    except PermissionError:
        pass

    try:
        ctx.domain.const_config.update({"a": 1})
        ctx.domain.test_status = "ERROR_CONST_UPDATED"
        return None
    except (PermissionError, AttributeError): 
        pass

    ctx.domain.test_status = "OK_WRITE_BLOCKED"
    return None

@process(inputs=["domain.internal_data", "domain.const_config"], outputs=["domain.test_status"])
async def p_try_read_zones(ctx):
    # READ const_ -> allowed
    _ = ctx.domain.const_config

    # READ internal_ -> non-admin -> should return None
    val = ctx.domain.internal_data
    if val is not None:
        ctx.domain.test_status = f"ERROR_INTERNAL_READ: {val}"
        return None
    
    ctx.domain.test_status = "OK_READ_BLOCKED"
    return None

@process(outputs=["domain.const_config", "domain.internal_data", "domain.test_status"])
async def p_admin_access(ctx):
    with AdminTransaction(ctx) as admin:
        # const_ write should STILL fail
        try:
            admin.domain.const_config = [1, 2]
            admin.domain.test_status = "ERROR_ADMIN_CONST_WRITTEN"
            return None
        except PermissionError:
            pass
            
        # internal_ read should SUCCEED
        val = admin.domain.internal_data
        if val != "secret":
            admin.domain.test_status = f"ERROR_ADMIN_INTERNAL_READ: {val}"
            return None
            
        # internal_ write should SUCCEED
        admin.domain.internal_data = "new_secret"
        
    ctx.domain.test_status = "OK_ADMIN"
    return None

import pytest

@pytest.mark.asyncio
async def test_zones():
    engine = TheusEngine(context={
        "domain": {
            "const_config": [0],
            "internal_data": "secret",
            "test_status": ""
        }
    })
    
    # 1. Non-admin process trying to write CONSTANT
    await engine.execute(p_try_write_zones)
    res = engine.state.data["domain"]["test_status"]
    assert res == "OK_WRITE_BLOCKED", f"Failed write test: {res}"
    
    # 2. Non-admin process trying to read PRIVATE
    await engine.execute(p_try_read_zones)
    res = engine.state.data["domain"]["test_status"]
    assert res == "OK_READ_BLOCKED", f"Failed read test: {res}"
    
    # 3. Admin process
    await engine.execute(p_admin_access)
    res = engine.state.data["domain"]["test_status"]
    assert res == "OK_ADMIN", f"Failed admin test: {res}"
    assert engine.state.data["domain"]["internal_data"] == "new_secret"
    
    print("ALL ZONE PHYSICS TESTS PASSED")

@process(outputs=["domain.const_data"])
async def p_mutate_override(ctx):
    # normally const_ blocked, but Mutable override allows UPDATE
    ctx.domain.const_data["updated"] = True
    return None

@pytest.mark.asyncio
async def test_annotated_overrides():
    domain_obj = OverrideDomain()
    domain_obj.const_data = {"a": 1}
    
    ctx = OverrideSystem(domain=domain_obj)
    engine = TheusEngine(context=ctx)
    
    await engine.execute(p_mutate_override)
    assert engine.state.data["domain"]["const_data"].get("updated") is True, "Failed to mutate const_data"
    print("ALL ANNOTATED OVERRIDE TESTS PASSED")

if __name__ == "__main__":
    asyncio.run(test_zones())
    asyncio.run(test_annotated_overrides())
