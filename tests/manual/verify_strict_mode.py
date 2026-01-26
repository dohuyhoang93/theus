import asyncio
from dataclasses import dataclass, field
from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class MyDomain(BaseDomainContext):
    items: list = field(default_factory=list)

@dataclass
class MyGlobal(BaseGlobalContext):
    pass

@dataclass
class MySystem(BaseSystemContext):
    domain_ctx: MyDomain = field(default_factory=MyDomain)
    global_ctx: MyGlobal = field(default_factory=MyGlobal)

# A process that tries to MUTATE in-place (Legacy Way)
@process(inputs=['domain.items'], outputs=['domain.items'])
async def legacy_mutation_process(ctx):
    print(f"  [Process] Type of ctx.domain.items: {type(ctx.domain.items)}")
    try:
        # Try to append directly
        ctx.domain.items.append("mutated")
        print("  [Process] Mutation SUCCESS (strict_mode=False behavior)")
        return "success"
    except (AttributeError, TypeError) as e:
        print(f"  [Process] Mutation BLOCKED ({type(e).__name__}): {e}")
        raise

async def test_strict_mode(enabled: bool):
    print(f"\n--- Testing strict_mode={enabled} ---")
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_mode=enabled)
    engine.register(legacy_mutation_process)
    
    try:
        await engine.execute("legacy_mutation_process")
        print("Result: EXECUTION SUCCESS")
    except Exception as e:
        print(f"Result: EXECUTION FAILED -> {type(e).__name__}")

async def main():
    # 1. Test Strict Mode (Should Fail/Block)
    await test_strict_mode(True)
    
    # 2. Test Loose Mode (Should Succeed)
    await test_strict_mode(False)

if __name__ == "__main__":
    asyncio.run(main())
