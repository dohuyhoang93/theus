import pytest
import asyncio
import sys
import os

# [Fix] Force test to use LOCAL SOURCE (not site-packages)
# This ensures we see the latest 'TheusEngine' signature (with strict_guards).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from theus import TheusEngine
from theus.contracts import process, ContractViolationError

# INTEGRATION TEST: Production Data Hazards
# Covers Chapter 07 Warnings:
# 1. Stale References (holding variable across awaits)
# 2. Silent Local Mutation (modifying read-only inputs)

# --- Processes ---

@process(inputs=['domain.test_list'], outputs=['domain.test_list'])
async def p_slow_updater(ctx):
    # Simulate work
    await asyncio.sleep(0.05)
    print(f"DEBUG: INSIDE UPDATOR - Before: {ctx.domain.test_list}")
    ctx.domain.test_list = [1, 2, 3] # Valid Update
    print(f"DEBUG: INSIDE UPDATOR - After: {ctx.domain.test_list}")
    return None # Was "UPDATED"

@process(inputs=['domain.test_list'], outputs=[]) # Read-Only (Safe)
async def p_stale_reader(ctx):
    # 1. Get Reference (Snapshot A)
    # This grabs a Shadow Copy of the list at Version T0
    my_ref = ctx.domain.test_list 
    
    # 2. Yield to allow p_slow_updater to run (Moves System to Version T1)
    await asyncio.sleep(0.1) 
    
    # 3. Try to use Stale Reference
    # Chapter 07 Warning: "Do not cache proxy object across await"
    # In Theus, 'my_ref' is isolated to Transaction A. 
    # Even though System is now T1 ([1,2,3]), 'my_ref' should still be T0 ([]).
    # This proves Snapshot Isolation.
    return my_ref

@process(inputs=['domain.test_list'], outputs=[]) # Read-Only
async def p_hacker_loop(ctx):
    # Try to append 100 items to read-only list
    # Chapter 07 Warning: "Silent Local Mutation"
    # Because 'items' is a Detached Copy, this succeeds locally.
    # WE verify that it is DISCARDED by engine.
    for i in range(100):
        ctx.domain.test_list.append(i)
    return "HACKED"

# --- Test Suite ---

@pytest.mark.asyncio
class TestProductionDataHazards:

    async def test_stale_reference_isolation(self):
        """
        Verify that holding a reference across awaits DOES NOT see concurrent updates.
        (Snapshot Isolation Integration / "Stale Ref Hazard" Check)
        """
        print("\n=== TEST: Stale Reference Isolation ===")
        ctx = {"domain": {"test_list": []}}
        engine = TheusEngine(context=ctx)
        engine.register(p_slow_updater)
        engine.register(p_stale_reader)
        
        # Launch both
        # Reader starts first, caches ref, sleeps Long
        t_read = asyncio.create_task(engine.execute(p_stale_reader))
        # Updater starts second, sleeps Short, Commits
        t_update = asyncio.create_task(engine.execute(p_slow_updater))
        
        # Wait
        results = await asyncio.gather(t_read, t_update)
        res_read, res_update = results
        
        print(f"DEBUG: Update Result: {res_update}")
        print(f"DEBUG: Current State: {engine.state.domain.test_list}")
        print(f"DEBUG: Current Version: {engine.state.version}")

        # 1. Verify Updater worked (Global State changed)
        assert engine.state.domain.test_list == [1, 2, 3]
        print("   [+] Global State Updated to [1, 2, 3]")
        
        # 2. Verify Reader saw OLD snapshot (Isolation)
        # It should NOT see [1, 2, 3] because it grabbed ref BEFORE update commit
        assert res_read == [], f"Stale Reference Leak! Reader saw {res_read}, expected []" 
        print(f"   [+] Reader safely isolated (Saw old state: {res_read})")

    async def test_silent_mutation_discard(self):
        """
        Verify that a 100-iteration mutation loop on Read-Only inputs is FULLY DISCARDED.
        (Silent Local Mutation Integration)
        """
        print("\n=== TEST: Silent Mutation Discard ===")
        import theus
        print(f"DEBUG: theus package file: {theus.__file__}")
        
        ctx = {"domain": {"test_list": []}}
        # Use Strict Guards to force Contract checks (Restored)
        engine = TheusEngine(context=ctx, strict_guards=True) 
        engine.register(p_hacker_loop)
        
        try:
            await engine.execute(p_hacker_loop)
        except Exception as e:
            # We expect Contract Violation or similar because we modified domain without output decl
            # Or if implicit discard is active, it might succeed but discard updates.
            # INC-001 fixed Silent Loss for WRITABLEs. 
            # For READ-ONLY, it might trigger Contract Violation if diff is detected.
            print(f"   [+] Caught expected rejection: {type(e).__name__}")
            
        # CRITICAL CHECK: Database must be empty
        final_state = engine.state.domain.test_list
        assert final_state == [], f"Silent Mutation Leaked into DB! Found: {final_state}"
        print("   [+] Data Integrity Preserved (DB is empty)")

if __name__ == "__main__":
    # Manual run helper
    asyncio.run(TestProductionDataHazards().test_stale_reference_isolation())
    asyncio.run(TestProductionDataHazards().test_silent_mutation_discard())
