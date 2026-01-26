"""
Test Smart CAS với DIFFERENT ZONES để chứng minh partial merge hoạt động.

KEY INSIGHT từ Rust Code (engine.rs lines 157-168):
- key_last_modified tracks at TOP-LEVEL keys: "domain", "heavy" 
- NOT nested keys like "domain.counter" vs "domain.name"
- Vì vậy để Smart CAS cho phép merge, cần update KHÁC ZONE

Kịch bản:
- Thread A: update "domain" → version bumps
- Thread B: update "heavy" với stale version → SHOULD SUCCEED (different zone)
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from theus import TheusEngine

def test_smart_cas_different_zones():
    """
    Test Smart CAS allows merge when updating DIFFERENT ZONES.
    Thread A updates "domain", Thread B updates "heavy" with stale version.
    """
    print("\n=== TEST: Smart CAS - Different Zones (domain vs heavy) ===")
    
    engine = TheusEngine(strict_cas=False)
    
    # 1. Initial state with both domain and heavy
    initial_version = engine.state.version
    engine._core.compare_and_swap(initial_version, {
        "domain": {"counter": 100},
        "heavy": {"buffer_size": 1024}
    })
    ver_after_init = engine.state.version
    print(f"Initial: ver={ver_after_init}, domain.counter=100, heavy.buffer_size=1024")
    
    # 2. Thread A updates DOMAIN only
    engine._core.compare_and_swap(ver_after_init, {"domain": {"counter": 200}})
    ver_after_domain = engine.state.version
    print(f"After domain update: ver={ver_after_domain}")
    
    # 3. Thread B tries to update HEAVY with STALE version
    stale_version = ver_after_init  # This is outdated
    print(f"\nThread B attempting to update 'heavy' with stale version={stale_version}...")
    print(f"(Actual version is {ver_after_domain})")
    
    try:
        engine._core.compare_and_swap(stale_version, {"heavy": {"buffer_size": 2048}})
        result_buffer = engine.state.heavy.get("buffer_size") if engine.state.heavy else "N/A"
        print("\n✅ SMART CAS SUCCESS!")
        print("   'heavy' was updated even though version was stale.")
        print("   Reason: 'heavy' zone was not modified since stale_version.")
        print(f"   Final: ver={engine.state.version}, heavy.buffer_size={result_buffer}")
        # return True -> Removed for pytest compatibility
    except Exception as e:
        print(f"\n❌ Smart CAS REJECTED: {e}")
        # print("   This means key_last_modified is tracking at a different level than expected.")
        # return False
        raise AssertionError(f"Smart CAS REJECTED: {e}")

def test_smart_cas_same_zone_different_fields():
    """
    Test Smart CAS with SAME ZONE but DIFFERENT FIELDS.
    v3.1 Field-Level CAS: Should SUCCEED because different fields don't conflict.
    """
    print("\n=== TEST: Smart CAS - Same Zone, Different Fields (should succeed) ===")
    
    engine = TheusEngine(strict_cas=False)
    
    # 1. Initial state
    initial_version = engine.state.version
    engine._core.compare_and_swap(initial_version, {"domain": {"counter": 100, "name": "Alice"}})
    ver1 = engine.state.version
    print(f"Initial: ver={ver1}")
    
    # 2. Thread A updates domain.name (bumps version)
    engine._core.compare_and_swap(ver1, {"domain": {"name": "Bob"}})
    ver2 = engine.state.version
    print(f"After domain.name update: ver={ver2}")
    
    # 3. Thread B tries to update domain.counter with stale version
    # v3.1: This SHOULD SUCCEED because domain.counter was not modified
    stale = ver1
    print(f"Thread B updating 'domain.counter' with stale version={stale}...")
    
    try:
        engine._core.compare_and_swap(stale, {"domain": {"counter": 200}})
        print("✅ Field-Level CAS SUCCESS! (different fields don't conflict)")
        # return True -> Removed for pytest compatibility
    except Exception as e:
        print(f"❌ UNEXPECTED REJECTION: {e}")
        # return False
        raise AssertionError(f"UNEXPECTED REJECTION: {e}")

if __name__ == "__main__":
    print("="*60)
    print("Smart CAS Key-Level Testing")
    print("="*60)
    
    results = []
    
    # Wrap in helper because functions now raise Exception on failure
    def run_safe(name, func):
        try:
            func()
            return True
        except AssertionError as e:
            print(f"Error in {name}: {e}")
            return False

    results.append(("Different Zones", run_safe("test_smart_cas_different_zones", test_smart_cas_different_zones)))
    results.append(("Same Zone, Different Fields", run_safe("test_smart_cas_same_zone_different_fields", test_smart_cas_same_zone_different_fields)))
    
    print("\n" + "="*60)
    print("SUMMARY:")
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    print("="*60)
    
    sys.exit(0 if all(r[1] for r in results) else 1)
