
"""
VERIFICATION SCRIPT: THEUS DORMANT POWER HYPOTHESIS
===================================================
Goal: Prove that Data Zone objects are IMMUTABLE (Frozen) by default
      and only become MUTABLE when activated by a valid Transaction (Output Declaration).

Scenarios:
1. [FAIL] External Mutation (Main Scope) -> Should raise PermissionError/ContextError
2. [FAIL] Illegal Process Mutation (No Output) -> Should raise PermissionError
3. [SUCCESS] Valid Process Mutation (With Output) -> Should succeed & Commit
4. [FAIL] Post-Process Mutation (Main Scope again) -> Should raise PermissionError

Result: If all assertions pass, the "Dormant Power" hypothesis is PROVEN.
"""

import pytest
import asyncio
from theus import TheusEngine, process
from theus.context import BaseDomainContext
from dataclasses import dataclass, field

# =============================================================================
# 1. Define Context with Data Zone
# =============================================================================

@dataclass
class MyDormantContext(BaseDomainContext):
    # Standard Data Zone (Mutable Potential)
    wallet: dict = field(default_factory=lambda: {"balance": 100})
    
    # Another Data Zone
    inventory: list = field(default_factory=list)

# =============================================================================
# 2. Define Processes (The Actors)
# =============================================================================

# Scenario 2: Illegal Process (No License)
@process(inputs=["domain.wallet"])  # Read-only license
async def p_hacker(ctx):
    print("\n[Hacker] Attempting to steal money...")
    try:
        ctx.domain.wallet["balance"] = 999999  # ILLEGAL WRITE
        return "Hacked"
    except Exception as e:
        print(f"[Hacker] BLOCK!: {e}")
        raise e

# Scenario 3: Valid Process (With License)
@process(inputs=["domain.wallet"], outputs=["domain.wallet"]) # Read-Write license
async def p_banker(ctx):
    print("\n[Banker] Depositing 50...")
    print(f"[DEBUG] Type of ctx.domain: {type(ctx.domain)}")
    print(f"[DEBUG] Type of ctx.domain.wallet: {type(ctx.domain.wallet)}")
    print(f"[DEBUG] Value of ctx.domain.wallet: {ctx.domain.wallet}")
    current = ctx.domain.wallet["balance"]
    ctx.domain.wallet["balance"] = current + 50  # VALID WRITE
    return None # Return None to avoid Functional State Update ambiguity

# =============================================================================
# 3. Main Verification Logic
# =============================================================================

async def run_proof():
    print(">>> 1. SETUP ENGINE")
    domain_ctx = MyDormantContext()
    # Mock Global Context
    from theus.context import BaseGlobalContext, BaseSystemContext
    global_ctx = BaseGlobalContext()
    
    # Wrap in System Context
    system_ctx = BaseSystemContext(global_ctx=global_ctx, domain=domain_ctx)
    print(f"DEBUG: System Context Dict: {system_ctx.to_dict()}")
    engine = TheusEngine(context=system_ctx)
    
    # -------------------------------------------------------------------------
    # Scenario 1: External Mutation (Main Scope)
    # -------------------------------------------------------------------------
    print("\n>>> 2. TEST EXTERNAL MUTATION (Main Scope)")
    try:
        # v3.0 API: use engine.state instead of engine.context
        print(f"Current Wallet: {engine.state.domain.wallet}")
        engine.state.domain.wallet["balance"] = 0
        print("❌ FAILURE: External mutation allowed! (Security Hole)")
        exit(1)
    except Exception as e:
        print(f"✅ SUCCESS: External mutation blocked! Error: {e}")

    # -------------------------------------------------------------------------
    # Scenario 2: Illegal Process Mutation (No Output)
    # -------------------------------------------------------------------------
    print("\n>>> 3. TEST ILLEGAL PROCESS (Reading License Only)")
    try:
        await engine.execute(p_hacker)
        print("❌ FAILURE: Hacker succeeded! (Security Hole)")
        exit(1)
    except Exception as e:
        # Expecting AuditBlockError or PyPermissionError depending on config
        print(f"✅ SUCCESS: Hacker blocked! Error: {type(e).__name__} - {e}")

    # -------------------------------------------------------------------------
    # Scenario 3: Valid Process Mutation (With Output)
    # -------------------------------------------------------------------------
    print("\n>>> 4. TEST VALID PROCESS (Full License)")
    try:
        await engine.execute(p_banker)
        print("✅ SUCCESS: Banker executed successfully.")
    except Exception as e:
        print(f"❌ FAILURE: Banker blocked unexpectedly! Error: {e}")
        exit(1)

    # -------------------------------------------------------------------------
    # Scenario 4: Post-Process Mutation (Main Scope again)
    # -------------------------------------------------------------------------
    print("\n>>> 5. TEST STATE AFTER COMMIT")
    
    try:
        # Use engine.state (Rust wrapper)
        # Note: engine.state.domain returns a proxy-like object? 
        # Actually it returns a LockedContextMixin-like view or Rust PyObject
        balance = engine.state.domain.wallet["balance"]
        print(f"Final Balance: {balance}")
        assert balance == 150, f"Expected 150, got {balance}"
        print("✅ SUCCESS: State updated correctly.")
    except Exception as e:
         print(f"❌ FAILURE: Could not read final state! {e}")
         exit(1)
         
    print("\n>>> 6. RE-VERIFY IMMUTABILITY")
    try:
        engine.state.domain.wallet["balance"] = -100
        print("❌ FAILURE: Post-commit mutation allowed!")
        exit(1)
    except Exception as e:
        print(f"✅ SUCCESS: Still immutable after commit. Error: {e}")

    print("\n" + "="*50)
    print("🏆 CONCLUSION: DORMANT POWER HYPOTHESIS PROVEN!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_proof())
