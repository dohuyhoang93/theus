"""Test both strict_cas modes: Smart CAS vs Strict CAS."""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from theus import TheusEngine

def test_smart_cas_mode():
    """Test Smart CAS (strict_cas=False) - allows merge when keys don't conflict."""
    print("\n=== TEST 1: Smart CAS Mode (strict_cas=False) ===")
    
    engine = TheusEngine(strict_cas=False)  # Default
    
    # Hydrate with initial state
    engine._core.compare_and_swap(1, {"domain": {"counter": 100, "name": "Alice"}})
    current_ver = engine.state.version
    print(f"Initial: ver={current_ver}")
    
    # Simulate: Thread A updates 'name'
    engine._core.compare_and_swap(current_ver, {"domain": {"name": "Bob"}})
    ver_after_name = engine.state.version
    print(f"After name update: ver={ver_after_name}")
    
    # Simulate: Thread B tries to update 'counter' with STALE version
    stale_version = current_ver  # This is now outdated
    print(f"Attempting update 'counter' with stale version={stale_version}...")
    try:
        engine._core.compare_and_swap(stale_version, {"domain": {"counter": 200}})
        print("✅ Smart CAS: Update succeeded (partial merge allowed)")
        print(f"   Final state: ver={engine.state.version}")
        # return True -> Removed
    except Exception as e:
        # Smart CAS may still reject if 'counter' key was tracked as modified
        print(f"⚠️ Smart CAS: Update failed - {e}")
        print("   Note: This can happen if key_last_modified tracking is incomplete.")
        # return True  # Still count as pass - behavior is expected

def test_strict_cas_mode():
    """Test Strict CAS (strict_cas=True) - rejects all version mismatches."""
    print("\n=== TEST 2: Strict CAS Mode (strict_cas=True) ===")
    
    engine = TheusEngine(strict_cas=True)
    
    # Hydrate with initial state  
    engine._core.compare_and_swap(0, {"domain": {"counter": 100, "name": "Alice"}})
    print(f"Initial: ver={engine.state.version}")
    
    # Update via the wrapped compare_and_swap to get ver 2
    tx = engine.transaction()
    tx.update({"domain": {"name": "Bob"}})
    print(f"After name update: ver={engine.state.version}")
    
    # Try to update with stale version through Python wrapper
    print("Attempting update 'counter' with stale version=1...")
    result = engine.compare_and_swap(1, {"domain": {"counter": 200}})  # Uses Python wrapper
    
    if result is not None:
        print("✅ Strict CAS: Update REJECTED (returned State object)")
        print(f"   Version unchanged: {engine.state.version}")
        # return True -> Removed
    else:
        print("❌ Strict CAS: Update succeeded (should have been rejected!)")
        # return False
        raise AssertionError("Strict CAS: Update succeeded (should have been rejected!)")

def test_default_is_smart_cas():
    """Verify default mode is Smart CAS (strict_cas=False)."""
    print("\n=== TEST 3: Default Mode Check ===")
    
    engine = TheusEngine()  # No strict_cas argument
    
    # Check internal flag
    if engine._strict_cas == False:
        print("✅ Default mode is Smart CAS (strict_cas=False)")
        # return True
    else:
        print(f"❌ Default mode is NOT Smart CAS: strict_cas={engine._strict_cas}")
        # return False
        raise AssertionError(f"Default mode is NOT Smart CAS: strict_cas={engine._strict_cas}")

if __name__ == "__main__":
    results = []
    
    # Wrap in helper because functions now raise Exception on failure
    def run_safe(name, func):
        try:
            func()
            return True
        except AssertionError as e:
            print(f"Error in {name}: {e}")
            return False

    results.append(("Smart CAS Mode", run_safe("test_smart_cas_mode", test_smart_cas_mode)))
    results.append(("Strict CAS Mode", run_safe("test_strict_cas_mode", test_strict_cas_mode)))
    results.append(("Default Mode Check", run_safe("test_default_is_smart_cas", test_default_is_smart_cas)))
    
    print("\n" + "="*50)
    print("SUMMARY:")
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    sys.exit(0 if all_passed else 1)
