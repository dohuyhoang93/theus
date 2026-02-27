"""
[Virtue Audit Step 1] Prove Severity: Does __dict__ mutation persist after commit?

This test answers the critical question:
If attacker does ctx.domain.__dict__['const_config'] = 'hacked',
does the mutation actually persist in committed state?
"""
import asyncio
from theus.engine import TheusEngine
from theus.contracts import process


@process(inputs=["domain.const_config", "domain.status"], outputs=["domain.status"])
async def p_dict_attack(ctx):
    """Attempt to mutate state via __dict__ backdoor."""
    # Step 1: Get raw dict via __dict__
    try:
        raw_dict = ctx.domain.__dict__
        print(f"[ATTACK] Got __dict__: type={type(raw_dict)}, keys={list(raw_dict.keys()) if isinstance(raw_dict, dict) else 'N/A'}")
    except PermissionError as e:
        print(f"[BLOCKED] __dict__ access blocked at ContextGuard level: {e}")
        ctx.domain.status = "BLOCKED_AT_GUARD"
        return None
    
    # Step 2: Try to mutate const_ field via raw dict
    original = raw_dict.get('const_config', 'NOT_FOUND')
    print(f"[ATTACK] Original const_config = {original}")
    
    try:
        raw_dict['const_config'] = 'HACKED_VIA_DICT'
        print("[ATTACK] Mutation succeeded in raw_dict!")
        print(f"[ATTACK] raw_dict['const_config'] = {raw_dict['const_config']}")
    except Exception as e:
        print(f"[BLOCKED] Mutation blocked: {e}")
        ctx.domain.status = "BLOCKED_AT_MUTATION"
        return None
    
    # Step 3: Check if mutation is visible through normal proxy access
    try:
        via_proxy = ctx.domain.const_config
        print(f"[CHECK] Via proxy after mutation: const_config = {via_proxy}")
    except Exception as e:
        print(f"[CHECK] Proxy access error: {e}")
    
    ctx.domain.status = "ATTACK_EXECUTED"
    return None


async def main():
    engine = TheusEngine(context={
        "domain": {
            "const_config": "original_secret",
            "status": "init",
        }
    })
    engine.register(p_dict_attack)
    
    # Capture state BEFORE
    state_before = engine.state.data["domain"]["const_config"]
    print(f"\n{'='*60}")
    print(f"[BEFORE] engine.state const_config = {state_before}")
    print(f"{'='*60}\n")
    
    try:
        await engine.execute(p_dict_attack)
    except Exception as e:
        print(f"[ENGINE] Execute error: {e}")
    
    # Capture state AFTER commit  
    state_after = engine.state.data["domain"]["const_config"]
    status = engine.state.data["domain"]["status"]
    print(f"\n{'='*60}")
    print(f"[AFTER] engine.state const_config = {state_after}")
    print(f"[AFTER] engine.state status = {status}")
    print(f"{'='*60}\n")
    
    # VERDICT
    if state_after == "original_secret":
        print("✅ VERDICT: __dict__ mutation did NOT persist. Severity = LOW")
        print("   CoW snapshot + commit-time enforcement prevented state corruption.")
    elif state_after == "HACKED_VIA_DICT":
        print("🚨 VERDICT: __dict__ mutation PERSISTED! Severity = CRITICAL")
        print("   Attack surface is real — must fix immediately.")
    else:
        print(f"⚠️ VERDICT: Unexpected state: {state_after}")


if __name__ == "__main__":
    asyncio.run(main())
