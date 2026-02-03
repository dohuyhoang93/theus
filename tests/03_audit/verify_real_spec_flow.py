"""
Real-World Audit Verification Script
=====================================
Tests the Active Audit Validator against the spec.yaml file.
Verifies that:
1. Level B (Block) with max_threshold=1 blocks on 2nd violation.
2. Level C (Count) never blocks, just counts.
3. Level S (Stop) blocks immediately on first violation.
4. Global Defaults are respected when no override is provided.
"""
import asyncio
import os
from theus import TheusEngine
from theus.contracts import process
from theus_core import AuditBlockError, AuditStopError

# --- Process Definitions ---
@process(inputs=['amount', 'dest'], outputs=['domain.balance'])
async def p_transfer(ctx, amount, dest):
    current = ctx.domain.balance or 0
    return current + amount

@process(inputs=['server'], outputs=['domain.status'])
async def p_critical(ctx, server):
    return "OK"


async def run_verify():
    print("=" * 60)
    print("   REAL-WORLD AUDIT VERIFICATION".center(60))
    print("=" * 60)
    
    spec_path = os.path.abspath("tests/03_audit/resources/audit_spec.yaml")
    print(f"[*] Spec File: {spec_path}")
    
    # =================================================================
    # TEST 1: Level B (Block) - max_threshold=1
    # =================================================================
    print("\n" + "-" * 60)
    print("TEST 1: Level B (Block) - max_threshold=1")
    print("-" * 60)
    
    engine = TheusEngine(
        context={"domain": {"balance": 0}},
        strict_guards=True,
        audit_recipe=spec_path
    )
    engine.register(p_transfer)
    engine.register(p_critical)
    
    # Violation 1: amount=50 < 100. Count=1. SHOULD PROCEED.
    print("[1.1] Triggering Violation 1 (amount=50)...")
    result = await engine.execute(p_transfer, amount=50, dest="UserA")
    print(f"      Result: {result} <- PROCEEDED (Count 1 <= Max 1)")
    
    # Violation 2: amount=50 again. Count=2 > Max 1. SHOULD BLOCK.
    print("[1.2] Triggering Violation 2 (amount=50)...")
    try:
        await engine.execute(p_transfer, amount=50, dest="UserA")
        print("      [FAIL] DID NOT BLOCK!")
    except AuditBlockError as e:
        print(f"      [PASS] BLOCKED: {e}")
    
    # =================================================================
    # TEST 2: Level C (Count) - Never Blocks
    # =================================================================
    print("\n" + "-" * 60)
    print("TEST 2: Level C (Count) - Never Blocks")
    print("-" * 60)
    
    # Create fresh engine to reset counts
    engine2 = TheusEngine(
        context={"domain": {"balance": 0}},
        strict_guards=True,
        audit_recipe=spec_path
    )
    engine2.register(p_transfer)
    
    # Trigger 10 violations on `dest` field (Level C)
    print("[2.1] Triggering 10 violations on 'dest' field (Level C)...")
    for i in range(10):
        # amount=100 is valid, dest="Admin" is invalid
        result = await engine2.execute(p_transfer, amount=100, dest="Admin")
    
    print(f"      [PASS] 10 violations, NO BLOCK. Balance: {engine2.state.domain.balance}")
    
    # =================================================================
    # TEST 3: Level S (Stop) - Immediate Halt
    # =================================================================
    print("\n" + "-" * 60)
    print("TEST 3: Level S (Stop) - Immediate Halt")
    print("-" * 60)
    
    engine3 = TheusEngine(
        context={"domain": {"status": "INIT"}},
        strict_guards=True,
        audit_recipe=spec_path
    )
    engine3.register(p_critical)
    
    print("[3.1] Triggering Level S violation (server='DANGER')...")
    try:
        await engine3.execute(p_critical, server="DANGER")
        print("      [FAIL] DID NOT STOP!")
    except AuditStopError as e:
        print(f"      [PASS] STOPPED: {e}")
    
    # =================================================================
    # TEST 4: Audit Works with strict_guards=False
    # =================================================================
    print("\n" + "-" * 60)
    print("TEST 4: Audit Works with strict_guards=False")
    print("-" * 60)
    
    engine4 = TheusEngine(
        context={"domain": {"balance": 0}},
        strict_guards=False,  # <-- KEY DIFFERENCE
        audit_recipe=spec_path
    )
    engine4.register(p_transfer)
    
    # Violation 1: amount=50 < 100. Count=1. SHOULD PROCEED.
    print("[4.1] Triggering Violation 1 (amount=50) with strict_guards=False...")
    result = await engine4.execute(p_transfer, amount=50, dest="UserA")
    print(f"      Result: {result} <- PROCEEDED (Count 1 <= Max 1)")
    
    # Violation 2: amount=50 again. Count=2 > Max 1. SHOULD BLOCK.
    print("[4.2] Triggering Violation 2 (amount=50) with strict_guards=False...")
    try:
        await engine4.execute(p_transfer, amount=50, dest="UserA")
        print("      [FAIL] DID NOT BLOCK! Audit might be disabled with strict_guards=False!")
    except AuditBlockError as e:
        print("      [PASS] BLOCKED: Audit works INDEPENDENTLY of strict_guards!")
    
    # =================================================================
    # SUMMARY
    # =================================================================
    print("\n" + "=" * 60)
    print("   VERIFICATION COMPLETE".center(60))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_verify())
