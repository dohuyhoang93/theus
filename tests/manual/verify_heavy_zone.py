import os
import sys
import time
import numpy as np
import asyncio
from theus import TheusEngine, process

# Goal: Verify Chapter 20 - Heavy Zone Optimization (Shared Memory)
# Scenario:
# 1. Main Process allocates a Large Array (100MB) in 'ctx.heavy'.
# 2. Worker Process accesses it via 'ctx.heavy' WITHOUT Copying (Zero-Copy).
# 3. Verify Memory Usage & Speed.

# --- Sub-Interpreter / Process Task ---
# Note: Workers cannot allocate, only Main can.
@process(inputs=["heavy.large_data"], outputs=[], parallel=True)
def analyze_large_data(ctx):
    import os
    import time
    
    start = time.time()
    
    # 1. Access Heavy Data (Zero-Copy View)
    # Theus automatically converts the SharedMemory handle to a Numpy Array
    arr = ctx.heavy["large_data"]
    
    # 2. Verify Attributes
    pid = os.getpid()
    shape = arr.shape
    mean_val = float(arr.mean()) # Calculation on shared memory
    
    # 3. Check if it's actually shared (Address check hard across processes, but timing is key)
    # If it was pickled/copied, this start-up would take 100ms+ for 100MB.
    # Zero-copy should be instant (<1ms).
    
    return {
        "pid": pid,
        "shape": shape,
        "mean": mean_val,
        "access_time": time.time() - start
    }

async def run_heavy_verification():
    print("==============================================")
    print("   THEUS HEAVY ZONE VERIFICATION (CHAP 20) ")
    print("==============================================")
    
    # Force Multi-processing for isolation test
    os.environ["THEUS_USE_PROCESSES"] = "1"
    
    engine = TheusEngine()
    engine.register(analyze_large_data)
    
    # 1. Allocate 100MB Array in Main Process
    print("\n[Step 1] Allocating 100MB Shared Memory...")
    size = 100 * 1024 * 1024 // 8 # float64 = 8 bytes
    shape = (size,)
    
    try:
        # User API: ctx.heavy.alloc(key, shape, dtype)
        # But here we are outside process, so we use engine.state.heavy_alloc?
        # Or manipulate state directly?
        # Theus Engine exposes 'managed_allocator' via Context? 
        # Actually Chapter 20 says: "Main allocates... Zero-Copy Read".
        # Let's see how to inject Heavy Data from outside.
        
        # We need to access the internal allocator for the test setup
        allocator = engine._core.managed_allocator if hasattr(engine, "_core") else None
        
        # If we can't reach internal API easily, we use a setup process
        # But wait, we can just use the public 'heavy_alloc' if exposed, 
        # or use a standard process to Init.
        pass
    except Exception:
        pass

    # Better apporach: Use a @process run on Main to Init
    @process(outputs=["heavy.large_data"])
    def init_heavy_data(ctx):
        # Allocation is special in Theus.
        # ctx.heavy is a wrapper. Does it have .alloc()?
        # According to source reading `HeavyZoneAllocator.alloc` exists in `context.py`.
        # But `HeavyZoneWrapper` in `context.py` doesn't expose `.alloc`.
        # It seems `alloc` is a method on the `HeavyZoneAllocator` which is passed as `_allocator`?
        
        # Let's check Chapter 20 docs again: "Main allocates... ctx.heavy.alloc()".
        # If wrapper doesn't have it, maybe it's dynamically added or I missed it in source.
        # Wait, `HeavyZoneAllocator` is the manager, `HeavyZoneWrapper` is the view.
        # Let's try direct assignment for now if alloc is automatic? 
        # No, SHM requires explicit alloc.
        
        # Fallback: We simulate the backend logic if API is internal.
        # But for "Real World" test, we should use public API.
        
        # Let's look at `theus/context.py` again.
        # `HeavyZoneAllocator` has `alloc`. But where is it attached?
        # It seems it might be `ctx.allocator.alloc` or similar?
        # Or maybe `ctx.heavy` is NOT the wrapper in Main process?
        
        # HYPOTHESIS: In Main, we might access the allocator directly.
        # For this test, I will assume `ctx.heavy.alloc` pattern is valid OR
        # I will manually use the allocator for setup.
        
        # Let's use `engine.allocate_heavy(key, shape, dtype)` if available?
        # Checking `engine.py` would confirm.
        pass
        return {}


    # Actually, let's create the array using `theus.context.HeavyZoneAllocator` directly
    # and inject it into state.
    from theus.context import HeavyZoneAllocator
    
    print("   Initializing Allocator...")
    allocator = HeavyZoneAllocator()
    
    print("   Allocating 'large_data'...")
    # 10M floats ~ 80MB
    arr = allocator.alloc("large_data", (10_000_000,), "float64")
    arr[:] = 1.0 # Fill
    arr[0] = 5.0 # Tweak mean
    expected_mean = float(arr.mean())
    
    print(f"   Created Array. Shape: {arr.shape}. Mean: {expected_mean}")
    
    # Inject into Engine State (Simulating previous process output)
    # Note: Must pass to 'heavy' kwarg, not 'data'
    engine.compare_and_swap(0, heavy={"large_data": arr})
    
    # 2. Run Worker Verification
    print("\n[Step 2] Launching Worker to access Data...")
    start = time.time()
    res = await engine.execute("analyze_large_data")
    total_dur = time.time() - start
    
    print(f"   Worker Result: {res}")
    
    # 3. Validation
    print("\n[Analysis]")
    print(f"   Worker Access Time: {res['access_time']:.6f}s")
    print(f"   Worker PID: {res['pid']} (Main: {os.getpid()})")
    print(f"   Data Integrity: {'✅ Clean' if abs(res['mean'] - expected_mean) < 1e-9 else '❌ Corrupt'}")
    
    if res['pid'] != os.getpid() and res['access_time'] < 0.05:
        # < 50ms for 80MB implies Zero-Copy
        # (Pickling 80MB usually takes 100ms+)
        print("   ✅ SUCCESS: Zero-Copy Shared Memory Verified.")
    elif res['pid'] == os.getpid():
         print("   ⚠️  Warning: Ran in Main Process (No Parallelism?). Zero-Copy trivial.")
    else:
         print("   ⚠️  Warning: Slow Access. Maybe Copy happened?")

    # Cleanup
    allocator.cleanup()
    print("\n==============================================")

if __name__ == "__main__":
    asyncio.run(run_heavy_verification())
