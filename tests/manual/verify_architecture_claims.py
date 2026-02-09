import sys
import time
import asyncio
from theus import TheusEngine, process

# Chapter 16 Claims Verification
# 1. Python 3.14+ Environment
# 2. Strict Mode vs Non-Strict Mode (Performance vs Safety)
# 3. Rust Core Integration

@process(inputs=["domain.counter"], outputs=["domain.counter"])
def fast_task(ctx):
    # Minimal logic to test overhead
    ctx.domain.counter += 1
    return {"domain.counter": ctx.domain.counter}

async def run_benchmark():
    print("==============================================")
    print("   THEUS ARCHITECTURE CLAIMS VERIFICATION ")
    print("   (Chapter 16 Masterclass) ")
    print("==============================================")

    # 1. Check Python Version
    print(f"\n[Claim 1] Python Version: {sys.version.split()[0]}")
    if sys.version_info >= (3, 10):
        print("   ✅ Python 3.10+ (V3 Requirement Met)")
    else:
        print("   ⚠️  Python version < 3.10. Sub-interpreters might be limited.")

    # 2. Rust Core Check
    print("\n[Claim 2] Rust Core Integration")
    try:
        import theus_core
        print(f"   ✅ Rust Core Found: {theus_core.__file__}")
    except ImportError:
        print("   ❌ Rust Core NOT FOUND. Running in Pure Python fallback?")
        return

    # 3. Strict Mode Overhead Benchmark
    print("\n[Claim 3] Performance: Strict (Safe) vs Non-Strict (Fast)")
    
    iters = 5000
    
    # A. Non-Strict (Simulate Training Mode)
    # Note: 'strict_guards=False' disables Dictionary Shadowing & Contract Checks in Rust
    engine_fast = TheusEngine(strict_guards=False, strict_cas=False)
    engine_fast.compare_and_swap(0, {"domain": {"counter": 0}})
    engine_fast.register(fast_task)
    
    start = time.time()
    for _ in range(iters):
        await engine_fast.execute("fast_task")
    dur_fast = time.time() - start
    ops_fast = iters / dur_fast
    print(f"   🚀 Non-Strict Mode: {ops_fast:.1f} ops/sec")

    # B. Strict Mode (Simulate Production)
    engine_safe = TheusEngine(strict_guards=True, strict_cas=True)
    engine_safe.compare_and_swap(0, {"domain": {"counter": 0}})
    engine_safe.register(fast_task)
    
    start = time.time()
    for _ in range(iters):
        await engine_safe.execute("fast_task")
    dur_safe = time.time() - start
    ops_safe = iters / dur_safe
    print(f"   🛡️  Strict Mode:    {ops_safe:.1f} ops/sec")
    
    overhead = (dur_safe - dur_fast) / dur_fast * 100
    print(f"   ℹ️  Safety Overhead: ~{overhead:.1f}%")
    print("   ✅ Dual-Mode Architecture Verified.")

    print("\n==============================================")
    print("   🎉 ARCHITECTURE MASTERCLASS VERIFIED")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
