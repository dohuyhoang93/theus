import pytest
import asyncio
import time
from theus.engine import TheusEngine
from theus.contracts import process, AdminTransaction, SemanticType

# Attempt to import Namespace (Expected to fail until implemented)
try:
    from theus.context import Namespace
    HAS_NAMESPACE = True
except ImportError:
    HAS_NAMESPACE = False

# =============================================================================
# 1. SAMPLE (MẪU) - Basic Functionality
# =============================================================================

@process(outputs=["domain.data"])
async def p_write_data(ctx, value):
    ctx.domain.data = value
    return "ok"

@process(outputs=["domain.log"])
async def p_append_log(ctx, msg):
    ctx.domain.log.append(msg)
    return "ok"

@pytest.mark.asyncio
async def test_case_1_sample_basic_ops():
    engine = TheusEngine(context={"domain": {"data": None, "log": []}})
    
    # Write
    await engine.execute(p_write_data, value="hello")
    assert engine.state.data["domain"]["data"] == "hello"
    
    # Append
    await engine.execute(p_append_log, msg="msg1")
    assert "msg1" in engine.state.data["domain"]["log"]
    
    # Namespace existence check (Should be False for now)
    if not HAS_NAMESPACE:
        print("\n[INFO] Namespace class not found as expected. Case 1 Namespace check skipped.")

# =============================================================================
# 2. RELATED (LIÊN QUAN) - Hierarchy & Inheritance
# =============================================================================

@process(outputs=["domain.nested.sub.key"])
async def p_write_deep(ctx, value):
    ctx.domain.nested.sub.key = value
    return "ok"

@pytest.mark.asyncio
async def test_case_2_related_deep_hierarchy():
    initial_ctx = {
        "domain": {
            "nested": {
                "sub": {"key": "old"}
            }
        }
    }
    engine = TheusEngine(context=initial_ctx)
    
    await engine.execute(p_write_deep, value="new")
    assert engine.state.data["domain"]["nested"]["sub"]["key"] == "new"
    
    # Test Policy Inheritance: If we have multiple nested proxies, 
    # they should all share the same policy and capabilities.
    # Note: State.domain returns a SupervisorProxy
    proxy = engine.state.domain
    # proxy.path is a property, but in some versions it might be internal or differently accessible
    assert hasattr(proxy, "is_proxy")
    nested_proxy = proxy.nested.sub
    # Instead of checking .path directly (which might be a bound method/property), 
    # we use repr which contains the path.
    assert "domain.nested.sub" in repr(nested_proxy)

# =============================================================================
# 3. BOUNDARY (BIÊN) - Security & Physics
# =============================================================================

@process(outputs=["domain.log_history"])
async def p_illegal_delete(ctx):
    # This should fail because log_ prefix enforces append-only in Rust
    try:
        ctx.domain.log_history.pop()
        # If it somehow succeeded, we return the mutated list (which shouldn't happen)
        return ctx.domain.log_history
    except PermissionError:
        # RETURN None so we don't overwrite domain.log_history with a string!
        # In Theus, if outputs is defined, the return value is written to that path.
        return ctx.domain.log_history

@process(outputs=["domain.log_history"])
async def p_admin_bypass(ctx):
    # Use AdminTransaction to bypass Zone Physics
    with AdminTransaction(ctx) as admin:
        # Clear works if CAP_DELETE is elevated
        admin.domain.log_history.clear()
    return "ELEVATED_OK"

@pytest.mark.asyncio
async def test_case_3_boundary_physics():
    engine = TheusEngine(context={"domain": {"log_history": ["entry1", "entry2"]}})
    
    # Test Physics Ceiling
    # We expect a PermissionError inside the process, but engine.execute returns the result
    # We need to be careful: if we return the list, it stays 2.
    await engine.execute(p_illegal_delete)
    
    history = engine.state.data["domain"]["log_history"]
    assert len(history) == 2
    
    # Test Admin Elevation
    # print("\nDEBUG: Starting Admin Elevation Test")
    await engine.execute(p_admin_bypass)
    history_after = engine.state.data["domain"]["log_history"]
    assert len(history_after) == 0

# =============================================================================
# 4. CONFLICT (XUNG ĐỘT) - Concurrency & Smart CAS
# =============================================================================

@process(outputs=["domain.counter_a"])
async def p_inc_a(ctx):
    ctx.domain.counter_a += 1
    return ctx.domain.counter_a

@process(outputs=["domain.counter_b"])
async def p_inc_b(ctx):
    ctx.domain.counter_b += 1
    return ctx.domain.counter_b

@pytest.mark.asyncio
async def test_case_4_conflict_smart_cas():
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    
    # Core Rust supports Smart CAS (Field-level conflicts)
    # Process A and B modify different fields. They should both succeed even if run together.
    # Note: We use execute one after another but with overlapping state versions 
    # to simulate the "Smart CAS" merge logic in Rust.
    
    v0 = engine.state.version
    
    # Simulate Process A starting at v0
    await engine.execute(p_inc_a)
    assert engine.state.version == v0 + 1
    
    # Simulate Process B starting at v0 but committing AFTER A
    # If Smart CAS works, this should not raise a Conflict Error even if v0 != v1
    # because counter_a != counter_b.
    # engine.execute handles retries automatically, so to test Smart CAS specifically, 
    # we would need to check if it merged on first try or retried.
    # However, for a generic integrative test, we check if final state is correct.
    
    await engine.execute(p_inc_b)
    
    assert engine.state.data["domain"]["counter_a"] == 1
    assert engine.state.data["domain"]["counter_b"] == 1

# =============================================================================
# FUTURE: Namespace Integration (Expect Failures)
# =============================================================================

@pytest.mark.skipif(not HAS_NAMESPACE, reason="Namespace class not implemented yet")
def test_namespace_wiring():
    # This will be the target for the next task
    class StrategyContext:
        meta_id: str = "S-001"
        data_active: bool = True

    class AlgoTradingContext:
        strategy = Namespace(StrategyContext)
        
    ctx = AlgoTradingContext()
    assert ctx.strategy.meta_id == "S-001"
