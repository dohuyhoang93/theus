"""
THEUS v3.1 REAL-WORLD API VERIFICATION
======================================
This script demonstrates the actual behavior of Theus v3.1 APIs without mocks.
It covers:
1. App Developer API (`ctx` inside @process) - The Golden Path
2. System API (`state.domain` vs `state.domain_proxy`) - Difference in Safety
3. Strict CAS Mode - Version Control
"""
import sys
import os
import asyncio
from dataclasses import dataclass, field

# Setup path
sys.path.insert(0, os.path.abspath("."))

from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext
from theus.structures import ContextError

# --- SETUP CONTEXT ---
@dataclass
class MyDomain(BaseDomainContext):
    counter: int = 0
    nested: dict = field(default_factory=lambda: {"a": 1})

@dataclass
class MyGlobal(BaseGlobalContext):
    pass

@dataclass
class MyContext(BaseSystemContext):
    domain: MyDomain
    global_ctx: MyGlobal

# --- 1. APP DEVELOPER API (The Golden Path) ---
@process(inputs=['domain.counter'], outputs=['domain.counter', 'domain.nested.a'])
def app_logic_process(ctx):
    """
    Developer uses 'ctx'. Theus automatically provides the safe wrapper 
    (SupervisorProxy inside ContextGuard).
    """
    print(f"   [Process] Read ctx.domain.counter: {ctx.domain.counter}")
    
    # Mutation 1: Top-level field
    ctx.domain.counter += 1
    
    # Mutation 2: Nested dictionary (The tricky part!)
    # In v3.1, this is intercepted by SupervisorProxy -> Transaction
    ctx.domain.nested['a'] = 999 
    
    print(f"   [Process] Mutated local ctx.domain.counter -> {ctx.domain.counter}")
    print(f"   [Process] Mutated local ctx.domain.nested['a'] -> {ctx.domain.nested['a']}")
    ctx.domain.counter += 1
    # Check if we can read it back immediately (Optimistic Local Read)
    print(f"DEBUG: Local Read of counter: {ctx.domain.counter}")
    
    return ctx.domain.counter

async def run_app_developer_api():
    print("\n--- TEST 1: APP DEVELOPER API (ctx) ---")
    data = {"domain": {"counter": 10, "nested": {"a": 100}}}
    engine = TheusEngine(context=None) # We'll hydrate manually
    engine.compare_and_swap(0, data)
    
    print(f"1. Initial State: {engine.state.domain.counter}, {engine.state.domain.nested}")
    
    # Execute Process
    await engine.execute(app_logic_process)
    
    print(f"2. Final State:   {engine.state.domain.counter}, {engine.state.domain.nested}")
    
    if engine.state.domain.nested['a'] == 999:
        print("✅ SUCCESS: Nested mutation persisted correctly (Deep Persistence).")
    else:
        print("❌ FAILURE: Nested mutation LOST.")

# --- 2. SYSTEM API (Legacy vs Supervisor) ---
def run_system_api_safety():
    print("\n--- TEST 2: SYSTEM API SAFETY (Legacy vs Proxy) ---")
    
    engine = TheusEngine()
    data = {"domain": {"nested": {"secret": "safe"}}}
    engine.compare_and_swap(0, data)
    
    # A. Legacy API (state.domain)
    print("A. Testing Legacy API (state.domain)...")
    legacy = engine.state.domain
    print(f"   Type: {type(legacy)}")
    
    try:
        # Shallow Check: This is blocked
        legacy['nested'] = {}
    except Exception as e:
        print(f"   ✅ Shallow Mutation BLOCKED: {e}")
        
    # DEEP UNSAFETY CHECK
    print("   Attempting Deep Mutation (Legacy Backdoor)...")
    try:
        legacy['nested']['secret'] = "COMPROMISED"
        print("   ⚠️  WARNING: Legacy Deep Mutation SUCCEEDED (As expected for FrozenDict implementation).")
        print(f"   Current State Verification: {engine.state.domain['nested']['secret']}")
    except Exception as e:
        print(f"   Unexpected block: {e}")

    # Reset State
    engine.compare_and_swap(engine.state.version, {"domain": {"nested": {"secret": "safe"}}})

    # B. Supervisor API (state.domain_proxy)
    print("\nB. Testing Supervisor API (state.domain_proxy)...")
    proxy = engine.state.domain_proxy()
    print(f"   Type: {type(proxy)}")
    
    print("   Attempting Deep Mutation (Supervisor Guard)...")
    try:
        # WITHOUT Transaction, Supervisor should BLOCK this
        proxy.nested.secret = "HACKED"
        print("   ❌ FAILURE: Supervisor allowed mutation outside transaction!")
    except Exception as e:
        print(f"   ✅ Supervisor BLOCKED Deep Mutation: {e}")
    
    # Verify State Integrity
    current = engine.state.domain['nested']['secret']
    if current == "safe":
         print("   ✅ State Integrity Preserved.")
    else:
         print(f"   ❌ State was compromised: {current}")

# --- 3. STRICT CAS MODE ---
def run_strict_cas_test():
    print("\n--- TEST 3: STRICT CAS MODE ---")
    
    # Mode 1: Smart CAS (Default)
    print("A. Smart CAS (strict_cas=False)")
    eng_smart = TheusEngine(strict_cas=False)
    eng_smart.compare_and_swap(0, {"domain": {"a": 1, "b": 1}})
    ver = eng_smart.state.version
    
    # Bump version artificially
    eng_smart.compare_and_swap(ver, {"domain": {"b": 2}}) 
    current_ver = eng_smart.state.version # ver+1
    
    # Attemp update on UNCHANGED key 'a' using OLD version
    print(f"   Attempting update 'a' with STALE version {ver} (Current: {current_ver})...")
    try:
        eng_smart.compare_and_swap(ver, {"domain": {"a": 99}})
        print("   ✅ Smart CAS ALLOWED update (Non-conflicting key).")
    except Exception as e:
        print(f"   ❌ Smart CAS Blocked: {e}")

    # Mode 2: Strict CAS
    print("\nB. Strict CAS (strict_cas=True)")
    eng_strict = TheusEngine(strict_cas=True)
    eng_strict.compare_and_swap(0, {"domain": {"a": 1, "b": 1}})
    ver = eng_strict.state.version
    
    # Bump version
    eng_strict.compare_and_swap(ver, {"domain": {"b": 2}})
    current_ver = eng_strict.state.version
    
    # Attemp update on UNCHANGED key 'a' using OLD version
    print(f"   Attempting update 'a' with STALE version {ver} (Current: {current_ver})...")
    
    # Strict mode returns Current State on failure, or raises error?
    # Engine wrapper returns 'self.state' (truthy) if pre-flight fails.
    # Returns None on success.
    res = eng_strict.compare_and_swap(ver, {"domain": {"a": 99}})
    
    if res is not None:
         print("   ✅ Strict CAS REJECTED update (Version Mismatch).")
    else:
         print("   ❌ Strict CAS Allow update (Checking state...)")
         print(f"   State Value A: {eng_strict.state.domain['a']}")


async def main():
    await run_app_developer_api()
    run_system_api_safety()
    run_strict_cas_test()

if __name__ == "__main__":
    asyncio.run(main())
