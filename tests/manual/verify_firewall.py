import asyncio
import sys
import os
# Force local source to avoid site-packages mismatch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

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
    # Order matters for dataclass inheritance with defaults.
    # BaseSystemContext has: global_ctx, domain (no defaults)
    # To fix "non-default arg follows default", we must provide defaults for ALL if we provide for one,
    # OR rely on keyword init.
    
    # We override BOTH to give them defaults matchin Base names.
    global_ctx: MyGlobal = field(default_factory=MyGlobal)
    domain: MyDomain = field(default_factory=MyDomain)


# Only declare 'declared'
@process(inputs=["domain.declared"], outputs=[])
async def spy_process(ctx):
    print("    -> [Spy] Reading declared...")
    _ = ctx.domain.declared

    print("    -> [Spy] Trying to read SECRET (Undeclared)...")
    secret = ctx.domain.secret  # Should FAIL here in Strict Mode
    return "stole_secret"


async def run_test(strict):
    print(f"\n--- Testing Contract Enforcement | Strict: {strict} ---")
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_guards=strict)
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
