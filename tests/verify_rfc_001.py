import pytest
from theus.engine import TheusEngine
from theus.contracts import process, AdminTransaction
from theus.zones import ContextZone
import theus_core

@process(outputs=["domain.log_events"])
def process_log_append(ctx):
    # Should work (CAP_APPEND)
    ctx.domain.log_events.append("event_1")
    return None

@process(outputs=["domain.log_events", "domain._last_error"])
def process_log_delete(ctx):
    # Should fail (CAP_DELETE not in LOG zone physics)
    try:
        ctx.domain.log_events.pop()
        return ("failed_to_block", "failed_to_block")
    except PermissionError as e:
        return (None, f"blocked: {e}")

@process(outputs=["domain.log_events", "domain._last_error"])
def process_log_update(ctx):
    # Should fail (CAP_UPDATE not in LOG zone physics)
    try:
        ctx.domain.log_events[0] = "malicious_update"
        return ("failed_to_block", "failed_to_block")
    except PermissionError as e:
        return (None, f"blocked: {e}")

@process(outputs=["domain.log_events"])
def process_admin_bypass(ctx):
    # Fill something first
    ctx.domain.log_events.append("safe")
    
    # Use AdminTransaction to bypass
    with AdminTransaction(ctx) as admin_ctx:
        admin_ctx.domain.log_events.pop()
        admin_ctx.domain.log_events.clear()
    
    return None

import asyncio

@pytest.mark.asyncio
async def test_semantic_policy_enforcement():
    initial_state = {"domain": {"log_events": []}}
    print(f"DEBUG: Initial state={initial_state}")
    engine = TheusEngine(context=initial_state)
    print(f"DEBUG: Engine initialized. Version={engine.state.version}")
    print(f"DEBUG: Initial state data={engine.state.data}")
    
    # 1. Test Append (Allowed)
    res = await engine.execute(process_log_append)
    print(f"DEBUG: Append result={res}")
    assert res is None  # [v3.3.1] Fix for No-Auto-Assign
    
    # Get state from engine
    state_obj = engine.state
    print(f"DEBUG: Engine Version={state_obj.version}")
    state_data = state_obj.data
    import json
    # Use to_dict() if available or just raw print
    raw_data = state_data.to_dict() if hasattr(state_data, "to_dict") else state_data
    print(f"DEBUG: Full State Data={raw_data}")
    
    assert "event_1" in state_data["domain"]["log_events"]
    
    # 2. Test Delete (Blocked)
    res = await engine.execute(process_log_delete)
    last_err = engine.state.data["domain"]["_last_error"]
    print(f"DEBUG: Delete result={res}, LastErr={last_err}")
    assert "blocked" in last_err
    assert "DELETE capability required" in last_err
    
    # 3. Test Update (Blocked)
    res = await engine.execute(process_log_update)
    last_err = engine.state.data["domain"]["_last_error"]
    print(f"DEBUG: Update result={res}, LastErr={last_err}")
    assert "blocked" in last_err
    assert "UPDATE capability required" in last_err
    
    # 4. Test Admin Bypass
    res = await engine.execute(process_admin_bypass)
    assert res is None
    assert len(engine.state.data["domain"]["log_events"]) == 0

if __name__ == "__main__":
    # Run manual verification
    try:
        asyncio.run(test_semantic_policy_enforcement())
        print("SUCCESS: RFC-001 Semantic Policy Architecture verified.")
    except Exception as e:
        print(f"FAILURE: {e}")
        import traceback
        traceback.print_exc()
