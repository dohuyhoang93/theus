"""
THEUS v3.1 INTEGRATED BENCHMARK
===============================
Comparing Read Performance:
1. Legacy Owner Model (state.domain -> FrozenDict copy)
2. Supervisor Model (state.domain_proxy() -> Zero-copy Ref)

Goal: Verify the performance gains of the new architecture on the actual integrated system.
"""
import time
import secrets
import sys
import os

# Ensure we use the local build
sys.path.insert(0, os.path.abspath("."))

from theus_core import TheusEngine

# --- SETUP ---
DATA_SIZE = 10000 # Elements in list (Large enough to feel serialization pain)
ITERATIONS = 100000

def make_large_data():
    return {
        "counter": 0,
        "large_list": [secrets.token_hex(16) for _ in range(DATA_SIZE)],
        "nested": {
            "a": 1,
            "b": [1, 2, 3] * 100
        }
    }

print("1. Initializing Engine...")
engine = TheusEngine()
large_data = make_large_data()

print(f"2. Populating State (Size: {DATA_SIZE} items)...")
start = time.time()
engine.compare_and_swap(0, {"domain": large_data})
print(f"   Population took: {time.time() - start:.4f}s")

# --- BENCHMARKS ---

def bench_legacy_read():
    """Accessing state.domain (triggers serialization/copy)"""
    start = time.time()
    for _ in range(ITERATIONS // 10): # Slower, so fewer iters
        # Logic: state.domain creates a FrozenDict wrapper around a COPY of the data
        # actually State::domain getter calls FrozenDict::new(dict.unbind()) which wraps the existing dict?
        # Wait, in Rust code:
        # State::domain -> if dict: FrozenDict::new(dict.extract(py)?)
        # extract() keeps it or copies? PyDict::new_bound(py) creates new?
        # Actually State::data is Arc<PyObject>.
        # getter domain() logic:
        # match self.data.get("domain") {
        #    Some(val) => {
        #         if is_dict: let dict: Py<PyDict> = val.extract(py)?; let frozen = FrozenDict::new(dict); ...
        #    }
        # }
        # PyAny::extract for Py<T> clones the reference?
        # But FrozenDict is a wrapper.
        # The key cost in Legacy was often described as "Copy on Read" or "Serialization".
        # Let's see what the actual cost is.
        _ = engine.state.domain
    end = time.time()
    ops = ITERATIONS // 10
    return ops, end - start

def bench_supervisor_read():
    """Accessing state.domain_proxy() (Zero-copy Ref)"""
    start = time.time()
    for _ in range(ITERATIONS):
        # SupervisorProxy just wraps the Py<PyAny>
        _ = engine.state.domain_proxy()
    end = time.time()
    return ITERATIONS, end - start

def bench_legacy_access():
    """Deep Access: state.domain['nested']['a']"""
    start = time.time()
    state = engine.state
    # We pull domain once to be fair? No, usually access pattern is engine.state.domain...
    # But let's verify repeated access cost.
    for _ in range(ITERATIONS // 10):
        d = state.domain
        _ = d['nested']['a']
    end = time.time()
    ops = ITERATIONS // 10
    return ops, end - start

def bench_supervisor_access():
    """Deep Access: state.domain_proxy().nested.a"""
    start = time.time()
    state = engine.state
    for _ in range(ITERATIONS):
        p = state.domain_proxy()
        _ = p.nested.a
    end = time.time()
    return ITERATIONS, end - start

# --- EXECUTION ---

print("\n--- TEST 1: GETTER LATENCY (ops/sec) ---")
leg_ops, leg_time = bench_legacy_read()
print(f"Legacy (FrozenDict): {leg_ops} ops in {leg_time:.4f}s => {leg_ops/leg_time:,.0f} ops/s")

sup_ops, sup_time = bench_supervisor_read()
print(f"Supervisor (Proxy):  {sup_ops} ops in {sup_time:.4f}s => {sup_ops/sup_time:,.0f} ops/s")

speedup = (sup_ops/sup_time) / (leg_ops/leg_time)
print(f"SPEEDUP: {speedup:.2f}x")


print("\n--- TEST 2: DEEP ACCESS LATENCY (ops/sec) ---")
leg_ops, leg_time = bench_legacy_access()
print(f"Legacy (['key']):      {leg_ops} ops in {leg_time:.4f}s => {leg_ops/leg_time:,.0f} ops/s")

sup_ops, sup_time = bench_supervisor_access()
print(f"Supervisor (.attr):    {sup_ops} ops in {sup_time:.4f}s => {sup_ops/sup_time:,.0f} ops/s")

speedup = (sup_ops/sup_time) / (leg_ops/leg_time)
print(f"SPEEDUP: {speedup:.2f}x")

if speedup < 1.0:
    print("\nWARNING: Supervisor is SLOWER. Check proxy overhead or getattr logic.")
else:
    print("\nSUCCESS: Supervisor architecture validates performance assumption.")
