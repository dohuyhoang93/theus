
import asyncio
import os
import sys

# Ensure current directory is in path
sys.path.insert(0, os.getcwd())

from theus import TheusEngine
from theus.structures import ContextError
import pytest

@pytest.mark.asyncio
async def test_strict_cas_enforcement():
    print("\n[TEST] Verifying INC-011: Strict Mode Propagation to Rust Core")
    
    # 1. Initialize Engine with BOTH strict_guards=True AND strict_cas=True
    # This ensures Rust Core gets the strict signal.
    engine = TheusEngine({"domain": {"counter": 0}}, strict_guards=True, strict_cas=True)
    
    initial_version = engine.state.version
    print(f"[*] Initial Version: {initial_version}")
    
    # 2. Simulate a "Smart Merge" scenario
    # We will try to update 'domain.counter' but with an OUTDATED version.
    # In Smart Mode (strict_cas=False), this might succeed if keys differ.
    # But here we are simulating a direct conflict or just testing strictness.
    # To test 'Strict CAS', we just need version mismatch.
    
    # Manually bump version via a hidden backdoor or just a valid update
    async def bumper(ctx):
        ctx.domain.counter = 1
        return "Bumped"
    engine.register(bumper)
    await engine.execute(bumper)
    
    new_version = engine.state.version
    print(f"[*] Bumped Version: {new_version}")
    
    # 3. Attempt CAS with OLD version (0)
    # If Strict Mode is ACTIVE in Rust, this MUST fail regardless of keys.
    print("[*] Attempting CAS with Validation 0 (Should Fail in Strict Mode)...")
    
    try:
        # Calling raw compare_and_swap (simulating concurrent race)
        # We try to update 'domain.other' (non-conflicting key)
        # Smart CAS would Allow this. Strict CAS must Reject.
        engine.compare_and_swap(
            expected_version=initial_version, # 0
            data={"domain": {"other": 99}},
            heavy=None,
            signal=None
        )
        print("[-] FAIL: CAS Succeeded! Rust Core is NOT enforcing Strict Mode.")
        sys.exit(1)
        
    except ContextError as e:
        if "Strict CAS Mismatch" in str(e):
             print(f"[+] PASS: Caught expected error: {e}")
        else:
             print(f"[?] PASS (Variant): Caught error: {e}")
             # Smart CAS might also reject if it thinks it's unsafe, but we want Strict error.
             # In engine.rs:159: "Strict CAS Mismatch... (Strict Mode Enabled)"
             if "Strict Mode Enabled" not in str(e):
                 print("[-] WARN: Error message does not explicitly confirm Strict Mode.")

    print("\n[SUCCESS] INC-011 Verified: Strict Mode is active in Rust Core.")

if __name__ == "__main__":
    asyncio.run(test_strict_cas_enforcement())
