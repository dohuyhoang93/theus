
import asyncio
import os
import sys

# Ensure current directory is in path
sys.path.insert(0, os.getcwd())

from theus import TheusEngine
from theus.structures import ContextError
import pytest

@pytest.mark.asyncio
async def test_strict_matrix():
    print("\n[TEST] Verifying Decoupled Strictness APIs (POP v3.1)")
    
    # CASE 1: Strict Guards=True, Strict CAS=False (Default Python, but requires decoupling)
    # Expected: 
    # - CAS should SUCCEED (Smart Mode) on minor mismatch.
    # - Note: We can't easily test Guards without complex inputs, focusing on CAS behavior.
    
    print("\n[-] CASE 1: Mode=True (Guards), CAS=False (Smart)")
    engine_1 = TheusEngine({"domain": {"counter": 0}}, strict_guards=True, strict_cas=False)
    
    # Bump version manually
    from theus.contracts import process
    
    @process(inputs=["domain"], outputs=["domain"])
    async def bumper(ctx): ctx.domain.counter = 1
    engine_1.register(bumper)
    await engine_1.execute(bumper)
    
    print("    [*] Attempting CAS with Old Version (Should SUCCEED due to Smart Mode)...")
    try:
        engine_1.compare_and_swap(
            expected_version=0, # Discrepancy (Current is 1)
            data={"domain": {"other": 99}}, # Non-conflicting key
            heavy=None, signal=None
        )
        print("    [+] PASS: Smart CAS Succeeded (as requested).")
    except ContextError as e:
        print(f"    [-] FAIL: Unexpected Strict Failure! {e}")
        sys.exit(1)

    # CASE 2: Strict Guards=True, Strict CAS=True (The Fix for INC-011)
    # Expected: CAS should FAIL.
    print("\n[-] CASE 2: Mode=True (Guards), CAS=True (Strict)")
    engine_2 = TheusEngine({"domain": {"counter": 0}}, strict_guards=True, strict_cas=True)
    
    # Bump
    @process(inputs=["domain"], outputs=["domain"])
    async def bumper2(ctx): ctx.domain.counter = 1
    engine_2.register(bumper2)
    await engine_2.execute(bumper2)
    
    print("    [*] Attempting CAS with Old Version (Should FAIL due to Strict Mode)...")
    try:
        engine_2.compare_and_swap(
            expected_version=0,
            data={"domain": {"other": 99}},
            heavy=None, signal=None
        )
        print("    [-] FAIL: CAS Succeeded! Should have failed.")
        sys.exit(1)
    except ContextError as e:
        if "Strict CAS" in str(e):
            print(f"    [+] PASS: Caught expected error: {e}")
        else:
            print(f"    [?] WARN: Caught unknown error: {e}")

    print("\n[SUCCESS] Strict Mode and Strict CAS are now DECOUPLED.")

if __name__ == "__main__":
    asyncio.run(test_strict_matrix())
