import asyncio
from dataclasses import dataclass, field
import sys
import os
# Force local source to avoid site-packages mismatch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext


@dataclass
class MyDomain(BaseDomainContext):
    data_items: list = field(default_factory=list)


@dataclass
class MyGlobal(BaseGlobalContext):
    pass


@dataclass
class MySystem(BaseSystemContext):
    global_ctx: MyGlobal = field(default_factory=MyGlobal)
    domain: MyDomain = field(default_factory=MyDomain)


# A process that tries to MUTATE in-place (Legacy Way)
@process(inputs=["domain.data_items"], outputs=["domain.data_items"])
async def legacy_mutation_process(ctx):
    print(f"  [Process] Type of ctx.domain.data_items: {type(ctx.domain.data_items)}")
    try:
        # Try to append directly
        ctx.domain.data_items.append("mutated")
        print("  [Process] Mutation SUCCESS (strict_guards=False behavior)")
        return ctx.domain.data_items
    except (AttributeError, TypeError) as e:
        print(f"  [Process] Mutation BLOCKED ({type(e).__name__}): {e}")
        raise


async def test_strict_guards(enabled: bool):
    print(f"\n--- Testing strict_guards={enabled} ---")
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_guards=enabled)
    engine.register(legacy_mutation_process)

    try:
        await engine.execute("legacy_mutation_process")
        print("Result: EXECUTION SUCCESS")
    except Exception as e:
        print(f"Result: EXECUTION FAILED -> {type(e).__name__}")


async def main():
    # 1. Test Strict Mode (Should Fail/Block)
    await test_strict_guards(True)

    # 2. Test Loose Mode (Should Succeed)
    await test_strict_guards(False)


if __name__ == "__main__":
    asyncio.run(main())
