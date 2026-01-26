"""
THEUS STANDARD VERIFICATION SUITE
=================================
This program verifies ALL state mutation mechanisms using standard Theus APIs.
No mocks. No hacks. Just pure Engine execution.

Mechanisms Tested:
1. Implicit POP (@process)      - Tier 1: Daily Driver
2. Batch Transaction (tx)       - Tier 2: Admin Tool
3. Safe Edit (edit)             - Tier 2: Debug Tool
4. Smart CAS (strict_cas=False) - Tier 3: High Concurrency
5. Strict CAS (strict_cas=True) - Tier 3: Critical Audit
"""

import sys
import os
import time

# Ensure we import from local build
sys.path.insert(0, os.path.abspath("."))

from theus import TheusEngine, ContractViolationError
from theus.contracts import process

from dataclasses import dataclass, field
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

# --- SETUP: Define Context & Process ---

@dataclass
class MyDomain(BaseDomainContext):
    counter: int = 0
    status: str = "init"
    config: dict = field(default_factory=lambda: {"mode": "default"})

@dataclass
class MyGlobal(BaseGlobalContext):
    pass

@dataclass
class MyContext(BaseSystemContext):
    pass

# Tier 1: Implicit POP Process
@process(inputs=['domain.counter'], outputs=['domain.counter', 'domain.status'])
def increment_process(ctx):
    """Tier 1: Standard Worker"""
    # 1. Read
    current = ctx.domain.counter
    
    # 2. Compute
    new_val = current + 1
    
    # 3. Return (Theus handles commit)
    return {
        "domain.counter": new_val,
        "domain.status": "processed"
    }

# --- VERIFICATION SUITE ---

import asyncio

async def verify_tier_1_implicit_pop(engine):
    print("\n--- [Tier 1] Implicit POP (@process) ---")
    
    # Debug Content
    try:
        current_data = engine.state.data # Rust State usually exposes .data
        print(f"DEBUG: Current State Keys: {current_data.keys()}")
    except AttributeError:
        # Fallback if .data is not exposed, try .domain alias if verified
        pass

    # Execute Async
    # Note: execute returns a coroutine even for sync functions if wrapped in @process
    result = await engine.execute(increment_process)
    
    # Check Result
    try:
        # Access via .data (standard Rust field name for domain zone)
        # Using .get for safety during debug
        # Note: Data structure mirrors SystemContext: {'domain': {...}, 'global_ctx': ...}
        domain_data = engine.state.data.get('domain', {})
        count = domain_data.get('counter', 'MISSING')
        status = domain_data.get('status', 'MISSING')
        
        print(f"After : counter={count}, status={status}")
        
        if count == 1 and status == "processed":
            print("✅ PASS: Implicit POP worked correctly.")
            return True
        else:
            print("❌ FAIL: Implicit POP failed (Value mismatch).")
            return False
    except Exception as e:
        print(f"❌ FAIL: Implicit POP failed (Check Error): {e}")
        return False

def verify_tier_2_transaction(engine):
    print("\n--- [Tier 2] Batch Transaction (tx.update) ---")
    
    with engine.transaction() as tx:
        tx.update({
            "domain": {
                "config": {"mode": "production", "shards": 5}
            }
        })
        
    cfg = engine.state.data.get('domain', {}).get('config')
    print(f"After : config={cfg}")
    
    if cfg and cfg['mode'] == "production":
        print("✅ PASS: Transaction committed successfully.")
        return True
    return False

def verify_tier_2_safe_edit(engine):
    print("\n--- [Tier 2] Safe Edit (engine.edit) ---")
    
    with engine.edit() as ctx:
        # Note: engine.edit() now yields the SystemContext directly
        # Access internal context directly
        ctx.domain.counter = 999
        
    domain_data = engine.state.data.get('domain', {})
    count = domain_data.get('counter')
    print(f"After : counter={count}")
    
    if count == 999:
        print("✅ PASS: Safe Edit modified state directly.")
        return True
    return False

def verify_tier_3_smart_cas(engine):
    print("\n--- [Tier 3] Smart CAS (strict_cas=False) ---")
    engine._strict_cas = False 
    
    ver_start = engine.state.version
    
    # A updates status
    engine.compare_and_swap(ver_start, {"domain": {"status": "thread_a"}})
    
    # B updates counter with OLD version
    res = engine.compare_and_swap(ver_start, {"domain": {"counter": 500}})
    
    if res is None:
        print("✅ PASS: Smart CAS allowed partial merge.")
        return True
    else:
        print(f"❌ FAIL: Smart CAS rejected. Res: {type(res)}")
        return False

def verify_tier_3_strict_cas(engine):
    print("\n--- [Tier 3] Strict CAS (strict_cas=True) ---")
    engine._strict_cas = True
    
    ver_start = engine.state.version
    
    # A updates status
    engine.compare_and_swap(ver_start, {"domain": {"status": "thread_x"}})
    
    # B updates counter with OLD version -> Must Fail
    # Note: State update failed above, so version bumped only once? 
    # Actually engine.compare_and_swap DOES bump version if success.
    
    res = engine.compare_and_swap(ver_start, {"domain": {"counter": 600}})
    
    if res is not None: 
        print("✅ PASS: Strict CAS rejected stale update.")
        return True
    else:
        print("❌ FAIL: Strict CAS allowed update!")
        return False

async def main():
    print("initializing Standard Theus Engine...")
    
    domain = MyDomain()
    gl = MyGlobal()
    ctx = MyContext(global_ctx=gl, domain=domain)
    
    engine = TheusEngine(context=ctx, strict_cas=False)
    
    # Verify Init
    print(f"Init State Keys: {engine.state.data.keys()}")
    
    print("Engine Ready.\n")
    
    results = []
    
    results.append(await verify_tier_1_implicit_pop(engine))
    results.append(verify_tier_2_transaction(engine))
    results.append(verify_tier_2_safe_edit(engine))
    results.append(verify_tier_3_smart_cas(engine))
    results.append(verify_tier_3_strict_cas(engine))
    
    print("\n" + "="*40)
    if all(results):
        print("🎉 ALL SYSTEMS GO: Standard Verification Passed.")
        sys.exit(0)
    else:
        print("💥 CRITICAL FAILURE: One or more mechanisms failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
