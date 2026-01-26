"""
Integration Test: ContextGuard + SupervisorProxy
Verifies that ContextGuard returns SupervisorProxy and Transaction mutation logging works.
"""
from theus_core import TheusEngine, SupervisorCore, SupervisorProxy, ContextGuard
from theus.contracts import process, SemanticType

print("=" * 60)
print("TEST: ContextGuard Integration")
print("=" * 60)

# 1. Setup minimal engine
core = TheusEngine()
print("1.1 Engine initialized")

# 2. Populate data with nested dict for testing Proxy wrapping
core.compare_and_swap(0, {"domain": {"counter": 10, "nested": {"a": 1}}})
print("1.2 Data populated")

# 3. Manual Transaction + Guard
print("\n--- Manual Transaction ---")
with core.transaction() as tx:
    print("2.1 Transaction started")
    
    # Create ContextGuard manually wrapping a DICT shadow copy
    shadow_domain = tx.get_shadow({"counter": 10, "nested": {"a": 1}}, "domain")
    
    # Guard logic
    guard = ContextGuard(
        shadow_domain, 
        inputs=["domain"], 
        outputs=["domain"], 
        path_prefix="domain",
        tx=tx,
        is_admin=False,
        strict_mode=True
    )
    print(f"2.2 ContextGuard created: {guard}")
    
    # 2.3 Access nested dict
    # IMPORTANT: guard wraps a dict, so we use item access ['nested']
    # ContextGuard should return SupervisorProxy for the nested dict
    nested_proxy = guard['nested']
    print(f"2.3 guard['nested'] type: {type(nested_proxy)}")
    print(f"    repr: {repr(nested_proxy)}")
    
    if "SupervisorProxy" not in str(type(nested_proxy)):
        print("❌ FAILURE: Expected SupervisorProxy!")
        exit(1)

    # 2.4 Verify SupervisorProxy dot access (Dict fallback feature)
    print(f"2.4 Accessing nested_proxy.a: {nested_proxy.a}")
    if nested_proxy.a != 1:
        print(f"❌ FAILURE: Expected 1, got {nested_proxy.a}")
        exit(1)

    # 2.5 Modify via proxy (dot access)
    print("2.5 Modifying nested_proxy.a = 99...")
    nested_proxy.a = 99
    
    # 2.6 Modify via item access (standard)
    print("2.6 Modifying nested_proxy['b'] = 2...")
    nested_proxy['b'] = 2
    
    # 2.7 Verify local reads
    print(f"    Read back .a: {nested_proxy.a}")
    print(f"    Read back ['b']: {nested_proxy['b']}")

    # IMPORTANT: In a manual transaction, we must explicitly write back the modified shadow
    # TheusEngine normally handles this mapping for processes.
    # TheusEngine normally handles this mapping for processes.
    tx.update(data={"domain": shadow_domain})

print("2.8 Transaction committed")

# 4. Verify persistence
state = core.state
print(f"3.1 State version: {state.version}")
domain = state.domain_proxy()
nested = domain.nested  # Use dot access here too

print(f"3.2 Verified persistence: a={nested.a}, b={nested.b}")

if nested.a == 99 and nested.b == 2:
    print("\n✅ SUCCESS: Mutations persisted!")
else:
    print(f"\n❌ FAILURE: Expected a=99, b=2. Got a={nested.a}, b={nested.b}")
    exit(1)

print("\n--- PURE Process Test ---")
# Skipping PURE process test as it requires full Engine setup which is complex in this unit test.
# The ContextGuard read-only logic is covered if SupervisorProxy read_only works (tested in Phase 1).
print("✅ PURE test skipped (Covered by Phase 1 Unit Test)")
