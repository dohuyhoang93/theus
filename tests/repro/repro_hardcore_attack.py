import asyncio
import ctypes
import gc
from theus import TheusEngine, process, BaseSystemContext
from theus.structures import FrozenDict
import theus_core
print(f"DEBUG: Loaded theus_core from: {theus_core.__file__}")

# 1. Setup Context
class VulnerableContext:
    def __init__(self):
        self.wallet = {"balance": 1000}  # Value target
        self.secret = ["nuclear_codes"] # Reference target

# Wrap in BaseSystemContext to satisfy Engine
system_ctx = BaseSystemContext({}, VulnerableContext())

engine = TheusEngine(system_ctx)

def get_ref_count(obj):
    return ctypes.c_long.from_address(id(obj)).value

async def attack_simulation():
    print(f"\n[ATTACK] Target Initial State: {engine.state.domain.wallet}")
    print(f"[ATTACK] Target Type: {type(engine.state.domain.wallet)}")

    # -------------------------------------------------------------------------
    # VECTOR 1: The "Unmasking" (Lột mặt nạ)
    # Attempt to access the raw object behind the proxy via descriptor
    # -------------------------------------------------------------------------
    print("\n>>> VECTOR 1: Accessing proxy._target (The Unmasking)")
    try:
        # Theus Rust struct has #[pyo3(get, name = "_target")] ?
        proxy = engine.state.domain.wallet
        raw_obj = proxy._target
        print(f"🔓 CRITICAL: Extracted raw object: {raw_obj}")
        
        # Mutation Attempt
        raw_obj['balance'] = 0
        print("❌ PWNED: State mutated via _target bypass!")
    except AttributeError as e:
        print(f"🛡️ BLOCKED: Cannot access _target. Error: {e}")
    except Exception as e:
        print(f"🛡️ BLOCKED: {type(e).__name__}: {e}")

    # Re-verify state
    print(f"Current Balance: {engine.state.domain.wallet['balance']}")
    if engine.state.domain.wallet['balance'] == 0:
        print("Combat Status: DEFEATED by Vector 1")
        return

    # -------------------------------------------------------------------------
    # VECTOR 2: The "Memory Surgeon" (Phẫu thuật bộ nhớ)
    # Using ctypes to modify memory at address
    # -------------------------------------------------------------------------
    print("\n>>> VECTOR 2: ctypes Injection (The Memory Surgeon)")
    
    try:
        # 1. Get address of the proxy
        proxy = engine.state.domain.wallet
        
        # 2. We need the address of the Dict inside the Proxy.
        # Since we failed to get _target, we have to guess or use GC.
        print("Attempting to locate referents via GC...")
        referents = gc.get_referents(proxy)
        target_dict = None
        for ref in referents:
            if isinstance(ref, dict) and ref.get('balance') == 1000:
                target_dict = ref
                print("🔓 FOUND internal dict via GC traversal.")
                break
        
        if target_dict:
            # Direct mutation
            target_dict['balance'] = -9999
            print("❌ PWNED: State mutated via GC + Direct Access!")
        else:
            print("🛡️ RESILIENT: GC did not reveal target dict (Rust wrapper might hide it).")

    except Exception as e:
        print(f"⚠️ Vector 2 Error: {e}")

    # Final Check
    print(f"\n[FINAL] Balance: {engine.state.domain.wallet['balance']}")
    if engine.state.domain.wallet['balance'] != 1000:
        print("💀 CONCLUSION: Theus is Dead.")
    else:
        print("🏆 CONCLUSION: Theus Survived.")

if __name__ == "__main__":
    asyncio.run(attack_simulation())
