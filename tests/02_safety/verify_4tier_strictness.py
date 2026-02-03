
import asyncio
import os
import sys
import unittest

# Ensure current directory is in path
sys.path.insert(0, os.getcwd())

from theus import TheusEngine, process
from theus.structures import ContextError, StateUpdate

# ---------------------------------------------------------
# SETUP: Mock Processes for Testing
# ---------------------------------------------------------

@process(inputs=['domain.counter'], outputs=['domain.counter'])
def p_increment(ctx):
    return StateUpdate(data={'domain.counter': ctx.domain.counter + 1})

@process(inputs=['domain.x'], outputs=['domain.x'])
def p_update_x(ctx, val):
    return StateUpdate(data={'domain.x': val})

@process(inputs=['domain.y'], outputs=['domain.y'])
def p_update_y(ctx, val):
    return StateUpdate(data={'domain.y': val})

# ---------------------------------------------------------
# TEST SUITE
# ---------------------------------------------------------

async def run_4tier_verification():
    print("\n[TEST] 4-Tier Strictness Verification Suite (POP v3.1)")
    print("======================================================")

    # ---------------------------------------------------------
    # TIER 1: STANDARD CASE (Case Mẫu)
    # Scenario: Normal operation, verify data update & audit (implicit).
    # ---------------------------------------------------------
    print("\n[TIER 1] Standard Case (Normal Flow)")
    engine = TheusEngine(
        context={"domain": {"counter": 0}},
        strict_guards=True, 
        strict_cas=False
    )
    engine.register(p_increment)
    
    res = await engine.execute(p_increment)
    
    print(f"    [DEBUG] Execute Result Type: {type(res)}")
    print(f"    [DEBUG] Execute Result: {res}")
    print(f"    [DEBUG] Engine Version: {engine.state.version}")
    print(f"    [DEBUG] Engine Data: {engine.state.data}")

    assert engine.state.data['domain']['counter'] == 1
    print(f"    [+] Success: Counter updated to {engine.state.data['domain']['counter']}")
    print("    [+] PASS: Tier 1 Standard Flow")

    # ---------------------------------------------------------
    # TIER 2: RELATED CASE (Case Liên Quan)
    # Scenario: Smart CAS acts as a Mediator for non-conflicting updates.
    # Tx A updates X. Tx B updates Y. Base version is same. Both should succeed.
    # ---------------------------------------------------------
    print("\n[TIER 2] Related Case (Smart CAS Merge)")
    engine = TheusEngine(
        context={"domain": {"x": 0, "y": 0}},
        strict_guards=True,
        strict_cas=False # Enable Smart CAS
    )
    
    # 1. Capture Base Version
    base_ver = engine.state.version
    print(f"    [*] Base Version: {base_ver}")

    # 2. Simulate User A (Updates X)
    engine.compare_and_swap(
        expected_version=base_ver,
        data={'domain': {'x': 10}}
    )
    print("    [+] User A updated X (Version bumped)")

    # 3. Simulate User B (Updates Y using OLD Base Version)
    # In Strict CAS, this would fail. In Smart CAS, it checks overlap.
    try:
        engine.compare_and_swap(
            expected_version=base_ver, # STALE VERSION!
            data={'domain': {'y': 20}}      # Diff Field
        )
        print("    [+] User B updated Y (Smart Merge Succeeded)")
    except ContextError as e:
        print(f"    [-] FAIL: Smart CAS failed to merge! {e}")
        sys.exit(1)

    # Verify Final State
    state = engine.state.data['domain']
    assert state['x'] == 10
    assert state['y'] == 20
    print(f"    [+] Final State: x={state['x']}, y={state['y']}")
    print("    [+] PASS: Tier 2 Related Flow")

    # ---------------------------------------------------------
    # TIER 3: EDGE CASE (Case Biên)
    # Scenario: Empty Update, New Keys
    # ---------------------------------------------------------
    print("\n[TIER 3] Edge Case (Boundaries)")
    
    # 3.1 Empty Update (Should be No-Op or Success)
    ver_before = engine.state.version
    engine.compare_and_swap(ver_before, data={})
    ver_after = engine.state.version
    
    if ver_before == ver_after:
        print("    [+] Empty update was No-Op (Version stable)")
    else:
        print(f"    [+] Empty update bumped version (Acceptable behavior)")

    # 3.2 Dynamic Key Creation (Data Zone allows expansion)
    engine.compare_and_swap(engine.state.version, data={'domain': {'new_key': 999}})
    assert engine.state.data['domain']['new_key'] == 999
    print("    [+] Dynamic Key Creation Succeeded")
    print("    [+] PASS: Tier 3 Edge Cases")

    # ---------------------------------------------------------
    # TIER 4: CONFLICT CASE (Case Mâu Thuẫn)
    # Scenario: Direct Race Condition on SAME field.
    # Must FAIL even in Smart CAS mode (Semantic Conflict).
    # ---------------------------------------------------------
    print("\n[TIER 4] Conflict Case (Direct Race)")
    
    # Reset
    engine = TheusEngine(
        context={"domain": {"balance": 100}},
        strict_guards=True,
        strict_cas=False
    )
    base_ver = engine.state.version
    
    # User A: Withdraw 10
    engine.compare_and_swap(base_ver, data={'domain': {'balance': 90}})
    print("    [+] User A withdraws (Balance=90)")
    
    # User B: Withdraw 20 (Using OLD version where balance was 100)
    # Updates 'domain.balance'. This CLASHES with User A's update.
    print("    [*] User B attempts withdraw (Stale Version)...")
    try:
        engine.compare_and_swap(
            expected_version=base_ver,
            data={'domain': {'balance': 80}}
        )
        print("    [-] FAIL: Update Succeeded! This is a Race Condition leak!")
        sys.exit(1)
    except Exception as e:
        # We expect a conflict error (ContextError or similar)
        print(f"    [+] PASS: Update Rejected as expected. Error: {e}")

    print("\n[SUCCESS] All 4 Tiers Verified Successfully.")

if __name__ == "__main__":
    asyncio.run(run_4tier_verification())
