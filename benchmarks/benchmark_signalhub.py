"""
Benchmark recv() vs recv_async() performance.
Run: python benchmarks/benchmark_signalhub.py
"""
import asyncio
import time
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theus import SignalHub


def benchmark_blocking_recv():
    """Benchmark blocking recv() throughput."""
    hub = SignalHub()
    rx = hub.subscribe()
    
    # Buffer is 100, so pre-publish 100 messages max
    count = 100
    for i in range(count):
        hub.publish(f"msg_{i}")
    
    start = time.perf_counter()
    
    for _ in range(count):
        rx.recv()
    
    elapsed = time.perf_counter() - start
    throughput = count / elapsed
    latency_us = (elapsed / count) * 1_000_000
    
    return {
        "method": "recv() blocking",
        "count": count,
        "throughput": throughput,
        "latency_us": latency_us,
        "total_time": elapsed
    }


async def benchmark_async_recv():
    """Benchmark async recv_async() throughput."""
    hub = SignalHub()
    rx = hub.subscribe()
    
    # Buffer is 100
    count = 100
    for i in range(count):
        hub.publish(f"msg_{i}")
    
    start = time.perf_counter()
    
    for _ in range(count):
        await rx.recv_async()
    
    elapsed = time.perf_counter() - start
    throughput = count / elapsed
    latency_us = (elapsed / count) * 1_000_000
    
    return {
        "method": "recv_async() native",
        "count": count,
        "throughput": throughput,
        "latency_us": latency_us,
        "total_time": elapsed
    }


async def benchmark_to_thread_recv():
    """Benchmark asyncio.to_thread(recv()) throughput."""
    hub = SignalHub()
    rx = hub.subscribe()
    
    # Pre-publish messages (reduced because to_thread is slow)
    count = 100
    for i in range(count):
        hub.publish(f"msg_{i}")
    
    start = time.perf_counter()
    
    for _ in range(count):
        await asyncio.to_thread(rx.recv)
    
    elapsed = time.perf_counter() - start
    throughput = count / elapsed
    latency_us = (elapsed / count) * 1_000_000
    
    return {
        "method": "asyncio.to_thread(recv())",
        "throughput": throughput,
        "latency_us": latency_us,
        "total_time": elapsed
    }


async def main():
    print("=" * 60)
    print("SignalHub Performance Benchmark")
    print("=" * 60)
    
    # Blocking recv
    print("\n[1/3] Benchmarking recv() blocking...")
    result1 = benchmark_blocking_recv()
    print(f"\n{result1['method']} (n={result1['count']})")
    print(f"  Throughput: {result1['throughput']:.0f} msgs/sec")
    print(f"  Latency:    {result1['latency_us']:.2f} μs")
    print(f"  Total time: {result1['total_time']:.3f} sec")
    
    # Async recv
    print("\n[2/3] Benchmarking recv_async() native...")
    result2 = await benchmark_async_recv()
    print(f"\n{result2['method']} (n={result2['count']})")
    print(f"  Throughput: {result2['throughput']:.0f} msgs/sec")
    print(f"  Latency:    {result2['latency_us']:.2f} μs")
    print(f"  Total time: {result2['total_time']:.3f} sec")
    
    # to_thread (for comparison)
    print("\n[3/3] Benchmarking asyncio.to_thread(recv())...")
    result3 = await benchmark_to_thread_recv()
    print(f"\n{result3['method']}")
    print(f"  Throughput: {result3['throughput']:.0f} msgs/sec")
    print(f"  Latency:    {result3['latency_us']:.2f} μs")
    print(f"  Total time: {result3['total_time']:.3f} sec")
    
    # Comparison
    print("\n" + "=" * 60)
    print("Comparison")
    print("=" * 60)
    
    overhead_pct = ((result2['latency_us'] / result1['latency_us']) - 1) * 100
    print(f"recv_async() vs recv():      {overhead_pct:+.1f}% latency")
    
    speedup = result2['throughput'] / result3['throughput']
    print(f"recv_async() vs to_thread(): {speedup:.1f}x faster")
    
    print("\n" + "=" * 60)
    print("Conclusion")
    print("=" * 60)
    
    if overhead_pct < 100:
        print(f"✅ recv_async() overhead is acceptable ({overhead_pct:+.1f}%)")
    else:
        print(f"⚠️  recv_async() overhead is high ({overhead_pct:+.1f}%)")
    
    if speedup > 10:
        print(f"✅ recv_async() much faster than to_thread() ({speedup:.1f}x)")
    else:
        print("⚠️  recv_async() not significantly faster than to_thread()")


if __name__ == "__main__":
    asyncio.run(main())
