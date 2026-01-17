import asyncio
from dataclasses import dataclass, field
from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class MyDomain(BaseDomainContext):
    declared: str = "allowed"
    secret: str = "forbidden"

@dataclass
class MyGlobal(BaseGlobalContext):
    pass

@dataclass
class MySystem(BaseSystemContext):
    domain_ctx: MyDomain = field(default_factory=MyDomain)
    global_ctx: MyGlobal = field(default_factory=MyGlobal)

# Only declare 'declared'
@process(inputs=['domain.declared'], outputs=[])
async def spy_process(ctx):
    print("    -> [Spy] Reading declared...")
    _ = ctx.domain.declared
    
    print("    -> [Spy] Trying to read SECRET (Undeclared)...")
    secret = ctx.domain.secret # Should FAIL here in Strict Mode
    return "stole_secret"

async def run_test(strict):
    print(f"\n--- Testing Contract Enforcement | Strict: {strict} ---")
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_mode=strict)
    engine.register(spy_process)
    
    try:
        await engine.execute("spy_process")
        print("    [Result] EXECUTION SUCCESS (Guard did not block)")
    except Exception as e:
        print(f"    [Result] BLOCKED: {type(e).__name__}: {e}")

async def main():
    # 1. Strict Mode -> Expect PermissionError
    await run_test(True)
    
    # 2. Loose Mode -> Expect Success? 
    # (Actually, even strict=False might block if Guard logic is generic? Let's see)
    await run_test(False)

if __name__ == "__main__":
    asyncio.run(main())
