import asyncio
import time
import threading
from theus import TheusEngine, process

# Goal: Verify Chapter 17 Claims
# 1. Async functions run on Event Loop.
# 2. Sync functions run in Thread Pool (don't block Loop).

@process(inputs=[], outputs=[])
async def async_worker(ctx):
    print(f"   [Async] Start sleeping 1s on Loop... (Thread: {threading.get_ident()})")
    await asyncio.sleep(1.0)
    print("   [Async] Done.")
    return {}

@process(inputs=[], outputs=[])
def sync_blocker(ctx):
    print(f"   [Sync] Start blocking 1s... (Thread: {threading.get_ident()})")
    # This blocks the thread. If running on Main Loop, it pauses everything.
    # If running in Thread Pool, Async Worker keeps running.
    time.sleep(1.0) 
    print("   [Sync] Done.")
    return {}

async def run_dispatch_verification():
    print("==============================================")
    print("   THEUS DISPATCHER VERIFICATION (CHAP 17) ")
    print("==============================================")
    
    engine = TheusEngine()
    engine.register(async_worker)
    engine.register(sync_blocker)
    
    print(f"   Main Thread ID: {threading.get_ident()}")
    
    # Scenario: Run both concurrently
    # If Sync runs on Main Thread, total time = 1s + 1s = 2s
    # If Sync runs on Thread Pool, they run in parallel -> Total time ~ 1s
    
    print("\n[Test] Running Async + Sync concurrently...")
    start = time.time()
    
    # We use asyncio.gather to schedule both
    await asyncio.gather(
        engine.execute("async_worker"),
        engine.execute("sync_blocker")
    )
    
    duration = time.time() - start
    print(f"\n   Total Duration: {duration:.2f}s")
    
    if duration < 1.2:
        print("   ✅ SUCCESS: Parallel execution confirmed (< 1.2s).")
        print("      Sync function was offloaded to Thread Pool.")
    elif duration >= 2.0:
        print("   ❌ FAILURE: Serial execution detected (~2.0s).")
        print("      Sync function blocked the Event Loop!")
    else:
        print("   ⚠️  INCONCLUSIVE: Duration unusual.")

    print("\n==============================================")

if __name__ == "__main__":
    asyncio.run(run_dispatch_verification())
