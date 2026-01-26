
import sys
import os

# Ensure we use the Local Source Code (with Hotfix & Init Patch)
sys.path.insert(0, os.path.abspath(".")) 

from theus import TheusEngine

def investigate_cas_failure():
    print("--- Starting CAS Investigation ---")
    
    # 1. Initialize Engine
    engine = TheusEngine()
    print("[1] Engine Initialized")
    
    # 2. Setup Initial State
    init_version = 0
    init_data = {"counter": 0, "status": "init"}
    engine._core.compare_and_swap(0, init_data) # Hydrate
    print(f"[2] Hydrated State: {engine.state.domain} (Ver: {engine.state.version})")
    
    # 3. Simulate Rival Update (Thread A updates state -> Ver 1)
    # We do this on main thread for simplicity
    tx = engine.transaction()
    tx.update({"domain": {"counter": 1, "status": "updated"}})
    print(f"[3] Rival Update Complete: {engine.state.domain} (Ver: {engine.state.version})")
    
    # Capture expected version for the VICTIM (which is the OLD version)
    expected_version = 0 
    
    # 4. Simulate Victim Update (Thread B tries to update using OLD version)
    print(f"[4] Victim Attempting CAS with expected_version={expected_version} (Actual={engine.state.version})...")
    
    victim_data = {"domain": {"counter": 999, "status": "stale_overwrite"}}
    
    # ATTEMPT CAS
    result = engine.compare_and_swap(
        expected_version=expected_version, 
        updates=victim_data
    )
    
    # 5. Analyze Result
    print(f"[5] CAS Result: {result}")
    print(f"[6] Final State Version: {engine.state.version}")
    
    # CAS Success = returns None (update applied)
    # CAS Failure = returns State object (rejection)
    if result is not None:
        print("\n[SUCCESS] CAS behaved correctly - Update REJECTED (returned State).")
        print("The hotfix is working: stale version was blocked.")
        sys.exit(0)
    else:
        # Check if data was actually updated
        domain = engine.state.domain
        if domain and domain.get('counter') == 999:
            print("\n[CRITICAL FAILURE] BUG REPRODUCED: CAS performed a 'Blind Write'!")
            print("Expected behavior: CAS should fail and NOT update.")
            sys.exit(1)
        else:
            print(f"\n[INFO] CAS returned None but counter is: {domain.get('counter') if domain else 'None'}")
            sys.exit(0)

if __name__ == "__main__":
    investigate_cas_failure()

