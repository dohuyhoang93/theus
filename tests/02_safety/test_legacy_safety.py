from theus_core import TheusEngine
import sys

engine = TheusEngine()
large_data = {"nested": {"a": 1}}
engine.compare_and_swap(0, {"domain": large_data})

print("1. Accessing Legacy Domain...")
# state.domain returns FrozenDict
domain = engine.state.domain
print(f"   Type: {type(domain)}")

print("2. Accessing Nested Dict...")
nested = domain['nested']
print(f"   Type: {type(nested)}")

print("3. Attempting Deep Mutation (Legacy)...")
try:
    nested['a'] = 999
    print("   ✅ Mutation SUCCEEDED (This proves Legacy is UNSAFE/SHALLOW)")
except Exception as e:
    print(f"   ❌ Mutation BLOCKED: {e}")

print(f"4. Verifying State Content: {engine.state.domain['nested']['a']}")
if engine.state.domain['nested']['a'] == 999:
    print("   CRITICAL: State was mutated in-place!")
else:
    print("   State remained immutable (Surprising?)")
