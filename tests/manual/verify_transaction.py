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
    data_list: list = field(default_factory=list)


@dataclass
class MyGlobal(BaseGlobalContext):
    pass


@dataclass
class MySystem(BaseSystemContext):
    global_ctx: MyGlobal = field(default_factory=MyGlobal)
    domain: MyDomain = field(default_factory=MyDomain)


# Process that mutates AND fails
@process(inputs=["domain.data_list"], outputs=["domain.data_list"])
async def process_that_crashes(ctx):
    print("    -> [Process] Appending 'bad_data'...")
    ctx.domain.data_list.append("bad_data")
    print("    -> [Process] 'bad_data' appended. Now raising ValueError...")
    raise ValueError("Intentional Crash to test Rollback")
    return "should_not_reach_here"


# Process that mutates successfully
@process(inputs=["domain.data_list"], outputs=["domain.data_list"])
async def process_success(ctx):
    ctx.domain.data_list.append("good_data")
    return ctx.domain.data_list


async def run_test(strict):
    print("\n========================================")
    print(f" TESTING TRANSACTION | Strict Guards: {strict}")
    print("========================================")

    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_guards=strict)
    engine.register(process_that_crashes)
    engine.register(process_success)

    # Initial State
    print(f"  [Init] Items: {sys_ctx.domain.data_list}")

    # Case 1: Crash -> Expect Rollback
    print("  [Step 1] Executing 'process_that_crashes'...")
    try:
        await engine.execute("process_that_crashes")
    except ValueError as e:
        print(f"  [Caught] Expected Error: {e}")

    # Check State
    # In V3 Architecture (Shadow Copy), the "bad_data" exists only in Shadow.
    # If Transaction failed/dropped, engine.state.domain (the Truth) should NOT change.
    # Note: sys_ctx is the INPUT object. Theus doesn't mutate it. We must check engine state.
    current_items = engine.state.domain.data_list
    print(f"  [Result] Items after Crash: {current_items}")

    if "bad_data" in current_items:
        print("  [FAIL] ❌ NO ROLLBACK! State is corrupted.")
    else:
        print("  [PASS] ✅ ROLLBACK SUCCESSFUL! State is clean.")

    # Case 2: Success
    print("  [Step 2] Executing 'process_success'...")
    await engine.execute("process_success")
    current_items = engine.state.domain.data_list
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
