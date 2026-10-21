"""INC-030 Burst Write Benchmark Suite

Measures sequential write scaling across multiple real-world access patterns:
1. SingleKeyBurst: same key updated N times (State size = 1 key)
2. DistinctKeyBurst: N distinct keys inserted (State size grows monotonically to N)
3. NestedDomainBurst: nested dict update (domain.counter)
4. ContextWithProxyBurst: Engine with populated context and domain proxy mutation
"""

import time
import statistics
import sys
from dataclasses import dataclass
from theus import TheusEngine, BaseDomainContext, BaseSystemContext

@dataclass
class BenchDomain(BaseDomainContext):
    counter: int = 0
    items: dict = None

@dataclass
class BenchContext(BaseSystemContext):
    domain: BenchDomain = None

def bench_single_key(n: int) -> float:
    e = TheusEngine()
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"counter": i})
    return time.perf_counter() - t0

def bench_distinct_keys(n: int) -> float:
    e = TheusEngine()
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={f"key_{i}": i})
    return time.perf_counter() - t0

def bench_nested_domain(n: int) -> float:
    e = TheusEngine()
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"domain": {"counter": i}})
    return time.perf_counter() - t0

def bench_context_sync(n: int) -> float:
    ctx = BenchContext(domain=BenchDomain(counter=0, items={}))
    e = TheusEngine(ctx)
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"domain": {"counter": i}})
    return time.perf_counter() - t0

def bench_prepopulated(initial_keys: int, n: int = 1000) -> float:
    e = TheusEngine()
    initial_dict = {f"k_{i}": i for i in range(initial_keys)}
    with e.transaction() as tx:
        tx.update(data=initial_dict)
    t0 = time.perf_counter()
    for i in range(n):
        with e.transaction() as tx:
            tx.update(data={"counter": i})
    return time.perf_counter() - t0

def bench_prepopulated_5000(n: int) -> float:
    return bench_prepopulated(5000, n)

def run_scenario(name: str, fn, n_list=[100, 500, 1000], reps=3):
    print("\n==========================================")
    print(f"Scenario: {name}")
    print("==========================================")
    for n in n_list:
        times = []
        for _ in range(reps):
            times.append(fn(n))
        med = statistics.median(times)
        mean = statistics.mean(times)
        per_op_us = (med / n) * 1e6
        print(f"  N={n:4d} | Median: {med:.4f}s | Mean: {mean:.4f}s | Per-op: {per_op_us:6.2f} µs")

def main():
    print("Starting INC-030 Burst Write Benchmark Suite (Python 3.14 + Theus Core)...")
    run_scenario("1. Flat Single Key (O(1) state size)", bench_single_key)
    run_scenario("2. Distinct Keys Growth (State size grows 1..N)", bench_distinct_keys)
    run_scenario("3. Nested Domain Dict (deep_merge_cow)", bench_nested_domain)
    run_scenario("4. Context + Proxy Sync (_sync_registry_from_core)", bench_context_sync)
    run_scenario("5. Prepopulated State (5,000 keys durable)", bench_prepopulated_5000, n_list=[100, 500, 1000], reps=3)

if __name__ == "__main__":
    main()

