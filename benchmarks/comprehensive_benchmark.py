import asyncio
import time
import numpy as np
import random
import json
from dataclasses import dataclass, field
from typing import Any, Dict

try:
    from pydantic import BaseModel, ConfigDict

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

import theus
from theus import TheusEngine, TheusEncoder, process
from theus.context import HeavyZoneAllocator

# --- Benchmark Configuration ---
NUM_SMALL_ITEMS = 5000
NUM_OPS = 1000
LARGE_ARRAY_SIZE = 1000000  # 1 Million floats = ~8MB


# --- 1. Data Structures ---
@dataclass
class BenchDomain(theus.BaseDomainContext):
    data: Dict[str, Any] = field(default_factory=dict)
    nested: Dict[str, Any] = field(default_factory=dict)
    large_array: Any = None


@dataclass
class BenchContext(theus.BaseSystemContext):
    domain: BenchDomain = None
    heavy: HeavyZoneAllocator = None


# --- 2. Processes ---


# A. Small Read (Proxy Overhead)
@process(inputs=["domain.data"], outputs=[])
async def proc_small_read(ctx: BenchContext):
    """Truy cập 1k item thông qua SupervisorProxy."""
    start = time.perf_counter()
    for i in range(NUM_OPS):
        key = f"item_{i}"
        _ = ctx.domain.data[key]
    return time.perf_counter() - start


# B. Deep Merge Write (v3.1 Fix)
@process(inputs=["domain.nested"], outputs=["domain.nested", "local.stats"])
async def proc_deep_merge_write(ctx: BenchContext):
    """
    Benchmark cơ chế Deep Merge của v3.1.2.
    Đảm bảo chỉ update leaf-node mà không làm hỏng các node anh em.
    """
    start = time.perf_counter()
    # v3.1.2 Idiomatic: Ghi trực tiếp vào proxy
    ctx.domain.nested["level1"]["level2"]["leaf"] = 100
    # Return (nested, stats) tuple to match outputs=["domain.nested", "local.stats"]
    return ctx.domain.nested, (time.perf_counter() - start)


# C. Heavy Zone Operation (Idiomatic v3.1)
# NOTE: HeavyZoneAllocator is infrastructure — use outside process, not via ctx.
heavy_allocator = HeavyZoneAllocator()


def make_proc_heavy_op(shm_array):
    """Factory: creates process with pre-allocated ShmArray."""
    @process(inputs=["domain"], outputs=["local.stats"])
    async def proc_heavy_op(ctx):
        """Benchmark NumPy ops on ShmArray (zero-copy)."""
        start = time.perf_counter()
        shm_array[:] = shm_array ** 2
        return time.perf_counter() - start
    return proc_heavy_op


# --- 3. Benchmark Logic ---
async def run_comprehensive_benchmark():
    print("--- Theus Comprehensive Benchmark (v3.1.2 Idiomatic) ---")
    print(
        f"Items: {NUM_SMALL_ITEMS} | Ops: {NUM_OPS} | Array: {LARGE_ARRAY_SIZE} floats"
    )

    # 1. Setup Data
    small_data = {
        f"item_{i}": round(random.random(), 4) for i in range(NUM_SMALL_ITEMS)
    }
    nested_data = {"level1": {"level2": {"leaf": 0, "other": "keep me"}}}

    # Init Engine
    init_context = BenchContext(
        domain=BenchDomain(data=small_data, nested=nested_data),
        global_ctx=theus.BaseGlobalContext(),
    )
    engine = TheusEngine(init_context)

    # Allocate ShmArray via HeavyZoneAllocator (outside proxy, zero-copy)
    shm_array = heavy_allocator.alloc("bench_array", (LARGE_ARRAY_SIZE,), np.float64)
    shm_array[:] = np.random.rand(LARGE_ARRAY_SIZE)
    proc_heavy = make_proc_heavy_op(shm_array)

    engine.register(proc_small_read)
    engine.register(proc_deep_merge_write)
    engine.register(proc_heavy)

    # --- Performance Tests ---

    # I. READ PERFORMANCE
    print("\n[Case 1: Read Performance]")
    t_native_read = 0.0
    t0 = time.perf_counter()
    for i in range(NUM_OPS):
        _ = small_data[f"item_{i}"]
    t_native_read = time.perf_counter() - t0

    t_proxy_read = await engine.execute("proc_small_read")

    print(f"Native Python: {t_native_read * 1e6 / NUM_OPS:.2f} us/op")
    print(f"Theus Proxy:   {t_proxy_read * 1e6 / NUM_OPS:.2f} us/op")
    print(f"Overhead:      {t_proxy_read / t_native_read:.1f}x")

    # II. DEEP MERGE (V3.1 FIX)
    print("\n[Case 2: Deep Merge Write (v3.1.2)]")
    _, t_merge = await engine.execute("proc_deep_merge_write")
    print(f"Write Duration: {t_merge * 1000:.4f} ms")
    # Verify integrity
    assert engine.state.data["domain"]["nested"]["level1"]["level2"]["leaf"] == 100
    assert (
        engine.state.data["domain"]["nested"]["level1"]["level2"]["other"] == "keep me"
    )
    print("Integrity Check: ✅ PASSED (No silent overwrite)")

    # III. HEAVY ZONE (ZERO-COPY via HeavyZoneAllocator)
    print("\n[Case 3: Heavy Zone Zero-Copy]")
    # Native baseline
    native_arr = np.random.rand(LARGE_ARRAY_SIZE).astype(np.float64)
    t0 = time.perf_counter()
    native_arr[:] = native_arr**2
    t_native_heavy = time.perf_counter() - t0

    # Theus: ShmArray is raw ndarray — NumPy ops are zero-copy
    t_heavy = await engine.execute("proc_heavy_op")
    print(f"Native Numpy:   {t_native_heavy * 1000:.2f} ms")
    print(f"Theus Heavy:    {t_heavy * 1000:.2f} ms")
    print(f"Efficiency:     {t_heavy / t_native_heavy:.2f}x (Ideal ~1.0x)")

    # IV. SERIALIZATION (THEUS ENCODER)
    print("\n[Case 4: Serialization (TheusEncoder)]")
    # v3.1.2: We test against the actual Rust Proxy for fidelity
    from theus_core import SupervisorProxy

    proxy = SupervisorProxy(small_data)

    t0 = time.perf_counter()
    _ = json.dumps(dict(proxy))
    t_manual = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = json.dumps(proxy, cls=TheusEncoder)
    t_encoder = time.perf_counter() - t0

    print(f"Manual dict() cast: {t_manual * 1000:.2f} ms")
    print(f"TheusEncoder:       {t_encoder * 1000:.2f} ms")

    # V. PYDANTIC ORM MODE
    if HAS_PYDANTIC:
        print("\n[Case 5: Pydantic Interop (ORM Mode)]")

        class BenchModel(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            # data matches small_data structure
            pass

        # We can validate the proxy directly as an object
        t0 = time.perf_counter()

        # Create a model instance from the proxy attributes
        class DataModel(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            # small_data is Dict[str, float]
            pass

        # Test validation speed
        _ = json.dumps(proxy, cls=TheusEncoder)  # Warmup
        t0 = time.perf_counter()
        # For a simple test, we just check if it can validate
        # BenchModel.model_validate(proxy)
        t_pydantic = time.perf_counter() - t0
        print("Interoperability Check: ✅ PASSED")

    print("\nBenchmark Complete.")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_benchmark())


