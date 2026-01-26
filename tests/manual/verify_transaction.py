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

# Process that mutates AND fails
@process(inputs=['domain.items'], outputs=['domain.items'])
async def process_that_crashes(ctx):
    print("    -> [Process] Appending 'bad_data'...")
    ctx.domain.items.append("bad_data")
    print("    -> [Process] 'bad_data' appended. Now raising ValueError...")
    raise ValueError("Intentional Crash to test Rollback")
    return "should_not_reach_here"

# Process that mutates successfully
@process(inputs=['domain.items'], outputs=['domain.items'])
async def process_success(ctx):
    ctx.domain.items.append("good_data")
    return "success"

async def run_test(strict):
    print("\n========================================")
    print(f" TESTING TRANSACTION | Strict Mode: {strict}")
    print("========================================")
    
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_mode=strict)
    engine.register(process_that_crashes)
    engine.register(process_success)
    
    # Initial State
    print(f"  [Init] Items: {sys_ctx.domain_ctx.items}")
    
    # Case 1: Crash -> Expect Rollback
    print("  [Step 1] Executing 'process_that_crashes'...")
    try:
        await engine.execute("process_that_crashes")
    except ValueError as e:
        print(f"  [Caught] Expected Error: {e}")
    
    # Check State
    # In V3 Architecture (Shadow Copy), the "bad_data" exists only in Shadow.
    # If Transaction failed/dropped, sys_ctx.domain_ctx (the Truth) should NOT change.
    current_items = sys_ctx.domain_ctx.items
    print(f"  [Result] Items after Crash: {current_items}")
    
    if "bad_data" in current_items:
        print("  [FAIL] ❌ NO ROLLBACK! State is corrupted.")
    else:
        print("  [PASS] ✅ ROLLBACK SUCCESSFUL! State is clean.")

    # Case 2: Success
    print("  [Step 2] Executing 'process_success'...")
    await engine.execute("process_success")
    current_items = sys_ctx.domain_ctx.items
    print(f"  [Result] Items after Success: {current_items}")
    
    if "good_data" in current_items:
        print("  [PASS] ✅ COMMIT SUCCESSFUL!")
    else:
        print("  [FAIL] ❌ COMMIT FAILED (Data missing).")

async def main():
    await run_test(strict=True)
    await run_test(strict=False)

if __name__ == "__main__":
    asyncio.run(main())
