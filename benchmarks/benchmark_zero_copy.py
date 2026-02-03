import time
import numpy as np
import multiprocessing
import multiprocessing.pool
import multiprocessing.shared_memory
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# Constants
MATRIX_SIZE = 3000  # 3000x3000 float64 ~ 72MB
NUM_WORKERS = 4


def output(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


# --- Tasks ---


def task_sequential_compute(arr):
    """Heavy Compute: Matrix Power"""
    return np.dot(arr, arr)


def task_io_bound(_):
    """IO Bound: Sleep"""
    time.sleep(0.5)
    return "done"


# --- Models ---


def run_sequential(arr):
    start = time.time()
    for _ in range(NUM_WORKERS):
        task_sequential_compute(arr)
    return time.time() - start


def run_threaded(arr):
    start = time.time()
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as exe:
        futures = [exe.submit(task_sequential_compute, arr) for _ in range(NUM_WORKERS)]
        [f.result() for f in futures]
    return time.time() - start


def _mp_worker(arr):
    return np.dot(arr, arr)


def run_multiprocessing_pickle(arr):
    """Standard MP (Deep Copy input)"""
    start = time.time()
    with multiprocessing.get_context("spawn").Pool(NUM_WORKERS) as p:
        # Note: 'arr' is pickled and sent to each worker
        results = [p.apply_async(_mp_worker, (arr,)) for _ in range(NUM_WORKERS)]
        [r.get() for r in results]
    return time.time() - start


# --- Zero Copy (Smart Pickle) ---


def _smart_worker(arr):
    # arr here is a ShmArray (reconstructed automatically via pickle)
    # This proves the "Engine Wiring" prevents the copy.
    res = np.dot(arr, arr)
    return res.shape


def run_smart_zerocopy(arr):
    """Uses Theus ShmArray to implicitly achieve Zero-Copy via Smart Pickling"""
    start = time.time()

    # 1. Promote to ShmArray (Theus "Heavy Zone" Logic)
    # Allocate Shared Memory
    shm = multiprocessing.shared_memory.SharedMemory(create=True, size=arr.nbytes)
    # Copy Data Once (Producer side)
    shared_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
    shared_arr[:] = arr[:]

    # Wrap in Theus Object
    from theus.context import ShmArray

    # Note: We must ensure 'shm' handle stays open while workers are using it?
    # Python pickle transfer: The worker opens its OWN handle via name.
    # The Main process must keep ITS handle open (or at least the file backing it must exist).
    # ShmArray holds 'shm'.
    theus_obj = ShmArray(shared_arr, shm=shm)

    prep_time = time.time() - start

    # 2. Workers (receive OBJECT, but Pickle magic sends REFERENCE)
    with multiprocessing.get_context("spawn").Pool(NUM_WORKERS) as p:
        results = [
            p.apply_async(_smart_worker, (theus_obj,)) for _ in range(NUM_WORKERS)
        ]
        [r.get() for r in results]

    total_time = time.time() - start

    # Cleanup
    shm.close()
    shm.unlink()

    return total_time, prep_time


# --- Full API Benchmark (TheusEngine) ---

from zc_tasks import process_heavy_task, process_simple_task


def run_theus_engine(arr):
    """Sử dụng TheusEngine + @process API (v3.1.2 Idiomatic)"""
    from theus.engine import TheusEngine
    from theus.context import (
        HeavyZoneAllocator,
        BaseSystemContext,
        BaseDomainContext,
        BaseGlobalContext,
    )
    import os

    # Bắt buộc dùng Multiprocessing vì NumPy hiện tại chưa hỗ trợ Sub-interpreters (Python 3.14)
    os.environ["THEUS_USE_PROCESSES"] = "1"

    start = time.time()

    # 1. Khởi tạo Engine với Context chuẩn
    from dataclasses import dataclass, field

    @dataclass
    class BenchDomain(BaseDomainContext):
        pass

    @dataclass
    class BenchGlobal(BaseGlobalContext):
        pass

    @dataclass
    class BenchContext(BaseSystemContext):
        domain: BenchDomain
        global_ctx: BenchGlobal
        # heavy zone được inject tự động bởi Engine

    ctx = BenchContext(domain=BenchDomain(), global_ctx=BenchGlobal())
    engine = TheusEngine(ctx, strict_guards=False)

    # 2. Inject Managed Memory (Producer side)
    # v3.1.2: Engine có Managed Allocator trong Core
    heavy_alloc = HeavyZoneAllocator()
    # Alloc & Copy
    shared_arr = heavy_alloc.alloc("matrix", arr.shape, arr.dtype)
    shared_arr[:] = arr[:]

    # Đồng bộ state (Ghi nhận SHM vào core)
    engine._core.compare_and_swap(
        engine.state.version, None, {"matrix": shared_arr}, None
    )

    prep_time = time.time() - start

    # 3. Register & Execute Parallel
    engine.register(process_heavy_task)

    # Case: Đo hiệu năng parallel execution
    output("Bắt đầu chạy Parallel Tasks qua Engine...")
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as exe:
        # execute_parallel sử dụng InterpreterPool hoặc ProcessPool tùy cấu hình
        # v3.1: execute_parallel is stateless, we must pass the data explicitly (via Zero-Copy ShmArray)
        futures = [
            exe.submit(engine.execute_parallel, "process_heavy_task", matrix=shared_arr)
            for _ in range(NUM_WORKERS)
        ]
        [f.result() for f in futures]

    total_time = time.time() - start

    # Cleanup SHM
    heavy_alloc.cleanup()

    return total_time, prep_time


# --- Main ---

if __name__ == "__main__":
    import sys
    import os

    sys.path.append(os.getcwd())

    print("=== THEUS V3.1.2 ZERO-COPY BENCHMARK ===")
    print(f"Ma trận: {MATRIX_SIZE}x{MATRIX_SIZE} | Số luồng: {NUM_WORKERS}")

    # Create Heavy Data
    data = np.random.rand(MATRIX_SIZE, MATRIX_SIZE)
    print(f"Kích thước dữ liệu: {data.nbytes / 1024 / 1024:.2f} MB")
    print("-" * 30)

    # 1. Sequential
    t_seq = run_sequential(data)
    print(f"1. Chạy tuần tự:    {t_seq:.4f}s (Gốc)")

    # 2. Threaded
    t_thread = run_threaded(data)
    print(f"2. Đa luồng (GIL):  {t_thread:.4f}s (Nhanh hơn: {t_seq / t_thread:.2f}x)")

    # 3. MP (Pickle)
    t_mp = run_multiprocessing_pickle(data)
    print(f"3. MP (Pickle):     {t_mp:.4f}s (Nhanh hơn: {t_seq / t_mp:.2f}x)")

    # 4. Zero Copy (Theus Core)
    t_zc, t_prep = run_smart_zerocopy(data)
    print(f"4. Theus Core ZC:   {t_zc:.4f}s (Nhanh hơn: {t_seq / t_zc:.2f}x)")
    print(f"   (Thời gian copy: {t_prep:.4f}s đã bao gồm)")

    print("-" * 30)

    # 5. Full API
    try:
        t_api, t_prep_api = run_theus_engine(data)
        print(f"5. Theus Engine API: {t_api:.4f}s (Nhanh hơn: {t_seq / t_api:.2f}x)")
        print(f"   (Overhead so với Core: {t_api - t_zc:.4f}s)")
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"5. Theus API:       THẤT BẠI ({e})")
