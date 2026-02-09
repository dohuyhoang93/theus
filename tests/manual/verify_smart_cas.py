import asyncio
import time
import pytest
from theus.engine import TheusEngine
from theus.structures import ContextError

def verify_smart_cas_logic():
    print("\n--- TEST 1: Smart CAS (Key-Level Optimism) ---")
    engine = TheusEngine()
    
    # 1. Setup Initial State: { "user": "A", "counter": 0 }
    engine.compare_and_swap(0, data={"user": "A", "counter": 0})
    initial_ver = engine.state.version
    print(f"Initial Version: {initial_ver}")
    
    # 2. Worker 1 Updates "user" -> "B" (Bumps Version)
    engine.compare_and_swap(initial_ver, data={"user": "B"})
    new_ver = engine.state.version
    print(f"Worker 1 Updated 'user'. Version: {new_ver} (Expected {initial_ver + 1})")
    
    # 3. Worker 2 Tries to Update "counter" -> 1
    # It uses OLD version (initial_ver), so Global Version Mismatch!
    # Smart CAS should allow this because "counter" wasn't touched by Worker 1.
    try:
        engine.compare_and_swap(initial_ver, data={"counter": 1})
        print("✅ Smart CAS Succeeded! (Merged safely due to disjoint keys)")
    except ContextError as e:
        print(f"❌ Smart CAS FAILED: {e}")
        return False
        
    # Verify State
    state = engine.state.data
    if state["user"] == "B" and state["counter"] == 1:
        print("   State Correct: {'user': 'B', 'counter': 1}")
    else:
        print(f"   ❌ State Corrupted: {state}")
        return False

    # 4. Conflict Case: Worker 3 tries to update "counter" using OLD version
    # Should FAIL because "counter" WAS modified in step 3.
    try:
        engine.compare_and_swap(initial_ver, data={"counter": 2})
        print("❌ Smart CAS Failed (False Positive - Should have rejected conflict)")
        return False
    except ContextError as e:
        print(f"✅ Smart CAS Correctly Rejected Conflict: {e}")
        
    return True


    
def verify_vip_ticket_logic():
    print("\n--- TEST 2: Priority Ticket (VIP System) ---")
    engine = TheusEngine()
    engine.compare_and_swap(0, data={"hot_key": 0})
    
    process_name = "struggling_worker"
    
    # 1. Simulate enough failures to TRIGGER VIP (logic requires count >= 5 before inc)
    print("Simulating 7 failures to guarantee VIP...")
    decision = None
    for i in range(7):
        decision = engine.report_conflict(process_name)
    
    print(f"Decision: {decision}")
    
    if decision.wait_ms > 10:
         print("⚠️ Warning: VIP might not have been granted? Wait time is high.")
    else:
         print("✅ VIP Likely Granted (Low wait time).")

    # 2. Attempt Write AS "struggling_worker" (Authenticated VIP)
    try:
        engine.compare_and_swap(engine.state.version, data={"hot_key": 999}, requester=process_name)
        print("✅ VIP Write Succeeded (Authenticated)")
    except Exception as e:
        print(f"❌ VIP Write Failed: {e}")
        return False
        
    # 3. Attempt Write AS Anonymous (Should be BLOCKED by VIP)
    print("Attempting Anonymous Write (Expect Failure)...")
    try:
        engine.compare_and_swap(engine.state.version, data={"hot_key": 888})
        print("❌ Anonymous Write Succeeded (Unexpected - Should be blocked by VIP!)")
        return False
    except ContextError as e:
        if "System Busy" in str(e):
             print(f"✅ Anonymous Write Correctly Blocked: {e}")
        else:
             print(f"⚠️ Write Failed but wrong error? {e}")
             
    engine.report_success(process_name) # Release VIP
    return True

if __name__ == "__main__":
    smart = verify_smart_cas_logic()
    vip = verify_vip_ticket_logic()
    
    if smart and vip:
        print("\nAll Tests Passed")
        exit(0)
    else:
        print("\nSome Tests Failed")
        exit(1)
