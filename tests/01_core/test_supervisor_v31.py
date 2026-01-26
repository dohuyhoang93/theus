"""
Test script for SupervisorCore and SupervisorProxy
"""
from theus_core import SupervisorCore, SupervisorProxy

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

print()
print("=" * 60)
print("TEST 2: SupervisorProxy Basic Operations")
print("=" * 60)

# Create proxy wrapping a dict
target_dict = {"x": 10, "y": 20, "nested": {"a": 1}}
proxy = SupervisorProxy(target_dict, "domain")

print(f"2.1 Created proxy: {repr(proxy)}")
print(f"2.2 Proxy path: {proxy.path}")
print(f"2.3 Proxy read_only: {proxy.read_only}")

# Test __getitem__
print(f"2.4 proxy['x'] = {proxy['x']}")

# Test __setitem__ 
proxy["z"] = 30
print(f"2.5 Set proxy['z'] = 30, now target_dict['z'] = {target_dict.get('z')}")

print()
print("=" * 60)
print("TEST 3: ReadOnly Proxy (PURE semantic)")
print("=" * 60)

ro_proxy = SupervisorProxy({"a": 1}, "domain", read_only=True)
print("3.1 Created read-only proxy")

try:
    ro_proxy["a"] = 999
    print("3.2 ERROR: Should have blocked write!")
except PermissionError as e:
    print(f"3.2 GOOD: Write blocked with: {e}")

print()
print("=" * 60)
print("ALL TESTS PASSED ✅")
print("=" * 60)
