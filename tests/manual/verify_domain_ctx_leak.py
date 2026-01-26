
import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath("."))

from theus import TheusEngine
from theus.contracts import process

@process(inputs=[], outputs=[])
def probe_context(ctx):
    results = {}
    
    # Check Types
    results['domain_type'] = str(type(ctx.domain))
    results['domain_ctx_type'] = str(type(ctx.domain_ctx))
    
    # Test 3: Check global_ctx access (Regression Test)
    try:
        # This was removed from Rust Core. Does it still work via alias?
        # If not, it means we broke API because ctx.global is syntax error.
        t = type(ctx.global_ctx)
        results['global_ctx_access'] = f"OK ({t})"
    except Exception as e:
        results['global_ctx_access'] = f"FAILED: {e}"
        
    # Test 1: Mutation on Safe 'domain' (SupervisorProxy)
    try:
        ctx.domain['counter'] = 999
        # In v3, this mutates the Transaction Shadow, not Global State.
        # Since outputs=[], this change is discarded.
        results['domain_mutation'] = "Allowed (Shadow Copy)"
    except Exception as e:
        results['domain_mutation'] = f"Blocked: {e}"
        
    # Test 2: Mutation on Legacy 'domain_ctx'
    try:
        ctx.domain_ctx['counter'] = 666
        results['domain_ctx_mutation'] = "Allowed (Shadow Copy)"
    except Exception as e:
        results['domain_ctx_mutation'] = f"Blocked: {e}"
        
    return results

async def verify_leak():
    print("=== Verifying domain_ctx vs domain behavior ===")
    
    # 1. Setup Engine with simple data
    engine = TheusEngine()
    engine._core.compare_and_swap(0, {"domain": {"counter": 100}})
    
    engine.register(probe_context)
    
    # Execute
    print("Executing probe...")
    # engine.execute is async
    results = await engine.execute("probe_context")
    
    print("\n[Probe Results]")
    for k, v in results.items():
        print(f"  {k}: {v}")
        
    print("-" * 30)
    
    # Check GLOBAL state 
    # v3.2: State is composed of Arc<PyObject>. If PyObject is dict, direct mutation inside same process 
    # (Threaded engine) MIGHT leak if it's the exact same object reference.
    # In 'spawn' mode (multiprocessing), leak wouldn't propagate back, but safety violation exists within worker.
    # TheusEngine default uses Threading if not parallel? 
    # Default is sequential/threaded unless parallel=True specified in @process or execute_parallel called.
    
    # engine.state.data returns a FrozenDict wrapper, but accessing via .data['domain'] 
    # might return the underlying Dict if called from internal Rust code properly?
    # engine.state is RestrictedStateProxy (Rust). 
    # Let's check via standard dictionary access if possible or helper.
    
    # We access via the exposed getter which returns SupervisorProxy/FrozenDict wrapper.
    # To check RAW value, we might need to bypass.
    # But if verify_domain_ctx_leak.py runs in same process, we can check.
    
    # Check via normal engine access
    try:
        current_val = engine.state.domain['counter']
        print(f"Global State 'counter' value: {current_val}")
        
        if current_val == 666:
            print("❌ CRITICAL: 'domain_ctx' allowed in-place mutation of Global State!")
        elif current_val == 999:
            print("❌ CRITICAL: 'domain' allowed in-place mutation!")
        elif current_val == 100:
            print("✅ Global State remains immutable (100).")
            # But did 'domain_ctx_mutation' say allowed?
            if results['domain_ctx_mutation'] == "Allowed (LEAK)":
                print("⚠️ WARNING: Local mutation was allowed (Reference Leak), even if not propagated or checked here.")
                print("   This means the process was working on a Mutable Reference!")
        else:
            print(f"❓ Unexpected value: {current_val}")
    except Exception as e:
        print(f"Error checking state: {e}")

if __name__ == "__main__":
    asyncio.run(verify_leak())
