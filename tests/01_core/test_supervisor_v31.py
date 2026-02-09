"""
Test script for SupervisorCore and SupervisorProxy
"""
import pytest
from theus_core import SupervisorCore, SupervisorProxy

class MockTransaction:
    def __init__(self):
        self.pending_delta = []
    def log_delta(self, path, old, new):
        self.pending_delta.append((path, old, new))

def test_supervisor_core_basic():
    print("=" * 60)
    print("TEST 1: SupervisorCore Basic Operations")
    print("=" * 60)

    core = SupervisorCore()

    # Write a dict
    core.write("domain", {"counter": 10, "name": "test"})
    print("1.1 Write domain: OK")

    # Read back
    data = core.read("domain")
    print(f"1.2 Read domain: {data}")

    # Check keys
    keys = core.keys()
    print(f"1.3 Keys: {keys}")

    # Check version
    ver = core.get_version("domain")
    print(f"1.4 Version: {ver}")

    # Update and check version increments
    core.write("domain", {"counter": 20})
    ver2 = core.get_version("domain")
    print(f"1.5 Version after update: {ver2} (should be > {ver})")

def test_supervisor_proxy_transactional():
    print()
    print("=" * 60)
    print("TEST 2: SupervisorProxy Transactional Operations")
    print("=" * 60)

    # Create proxy wrapping a dict
    target_dict = {"x": 10, "y": 20, "nested": {"a": 1}}
    tx = MockTransaction()
    
    # [RFC-001] Proxy now REQUIRE a transaction for mutations
    proxy = SupervisorProxy(target_dict, "domain", transaction=tx)

    print(f"2.1 Created proxy: {repr(proxy)}")
    print(f"2.2 Proxy path: {proxy.path}")
    
    # Test __getitem__
    print(f"2.4 proxy['x'] = {proxy['x']}")

    # Test __setitem__ (Should succeed WITH transaction)
    proxy["z"] = 30
    assert target_dict["z"] == 30
    print(f"2.5 Set proxy['z'] = 30, now target_dict['z'] = {target_dict.get('z')}")
    assert len(tx.pending_delta) > 0

def test_supervisor_proxy_read_only():
    print()
    print("=" * 60)
    print("TEST 3: ReadOnly Proxy (PURE semantic)")
    print("=" * 60)

    ro_proxy = SupervisorProxy({"a": 1}, "domain", read_only=True)
    print("3.1 Created read-only proxy")

    with pytest.raises(PermissionError) as excinfo:
        ro_proxy["a"] = 999
    print(f"3.2 GOOD: Write blocked with: {excinfo.value}")

def test_supervisor_proxy_no_transaction_blocks():
    """Verify that mutations without a transaction are blocked (Security Gate)."""
    proxy = SupervisorProxy({"x": 1}, "domain")
    with pytest.raises(PermissionError, match="No active transaction found"):
        proxy["x"] = 2

if __name__ == "__main__":
    # Allow manual running
    test_supervisor_core_basic()
    test_supervisor_proxy_transactional()
    test_supervisor_proxy_read_only()
    test_supervisor_proxy_no_transaction_blocks()
    print("\nALL TESTS PASSED ✅")
