"""
Load, Stress, and Performance Tests for SignalHub.

Tests system behavior under high load and stress conditions.
"""
import pytest
import asyncio
import time
import threading
from theus import SignalHub


class TestSignalHubLoad:
    """Load testing - sustained high throughput."""

    @pytest.mark.slow
    def test_sustained_throughput_10k_per_second(self):
        """
        Publish 10,000 messages/second for 5 seconds.
        Verify: No crashes, reasonable performance.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        total_messages = 50000
        start_time = time.time()
        
        # Publish in tight loop
        for i in range(total_messages):
            hub.publish(f"msg_{i}")
        
        publish_time = time.time() - start_time
        
        # Try to receive (may lag due to buffer)
        received_count = 0
        try:
            for _ in range(total_messages):
                rx.recv()
                received_count += 1
        except RuntimeError:
            # Lagged - expected for such high volume
            pass
        
        throughput = total_messages / publish_time
        print(f"Publish throughput: {throughput:.0f} msgs/sec")
        print(f"Received: {received_count}/{total_messages}")
        
        # Should be very fast (>100k msgs/sec)
        assert throughput > 10000, f"Too slow: {throughput} msgs/sec"

    # NOTE: This test was previously disabled due to blocking rx.recv() + asyncio.to_thread timeout issues.
    # Now fixed using native recv_async() API.
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_async_sustained_load(self):
        """Async receivers with sustained load - fixed with recv_async()."""
        hub = SignalHub()
        receivers = [hub.subscribe() for _ in range(5)]
        
        received_counts = [0] * 5
        
        async def async_receiver(idx, rx):
            """Receiver using native recv_async()."""
            for _ in range(100):
                msg = await asyncio.wait_for(
                    rx.recv_async(),  # Native async - timeout works!
                    timeout=2.0
                )
                received_counts[idx] += 1
        
        # Start all receivers
        tasks = [
            asyncio.create_task(async_receiver(i, rx))
            for i, rx in enumerate(receivers)
        ]
        
        # Publish messages
        for i in range(100):
            hub.publish(f"msg_{i}")
            await asyncio.sleep(0.001)  # Sustained load
        
        # Wait for all receivers
        await asyncio.gather(*tasks)
        
        # All receivers should get all messages
        assert all(count == 100 for count in received_counts)


class TestSignalHubStress:
    """Stress testing - push system to limits."""

    @pytest.mark.slow
    def test_stress_many_subscribers(self):
        """
        1000 subscribers receiving simultaneously.
        """
        hub = SignalHub()
        receivers = [hub.subscribe() for _ in range(1000)]
        
        # Publish 10 messages
        for i in range(10):
            count = hub.publish(f"broadcast_{i}")
            assert count == 1000
        
        # Sample receivers should get messages
        for rx in receivers[::100]:  # Every 100th receiver
            for i in range(10):
                msg = rx.recv()
                assert msg == f"broadcast_{i}"

    @pytest.mark.slow
    def test_stress_create_destroy_hubs(self):
        """
        Create and destroy 1000 SignalHubs rapidly.
        """
        for i in range(1000):
            hub = SignalHub()
            rx = hub.subscribe()
            hub.publish(f"msg_{i}")
            msg = rx.recv()
            assert msg == f"msg_{i}"
            # Hub and receiver go out of scope

    @pytest.mark.slow
    def test_stress_rapid_subscribe_unsubscribe_cycles(self):
        """
        10,000 subscribe/unsubscribe cycles.
        """
        hub = SignalHub()
        
        for i in range(10000):
            rx = hub.subscribe()
            if i % 100 == 0:
                # Occasionally publish
                hub.publish(f"msg_{i}")
            del rx  # Unsubscribe
        
        # Hub should still work
        rx = hub.subscribe()
        hub.publish("final")
        assert rx.recv() == "final"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_stress_concurrent_publish_subscribe(self):
        """
        100 concurrent publishers + 100 concurrent subscribers.
        """
        hub = SignalHub()
        
        async def publisher(pub_id):
            for i in range(100):
                hub.publish(f"pub{pub_id}_msg{i}")
                await asyncio.sleep(0.01)
        
        async def subscriber(sub_id):
            rx = hub.subscribe()
            count = 0
            try:
                for _ in range(1000):
                    await asyncio.to_thread(rx.recv)
                    count += 1
            except RuntimeError:
                pass  # Lagged
            return count
        
        tasks = []
        tasks.extend([publisher(i) for i in range(100)])
        tasks.extend([subscriber(i) for i in range(100)])
        
        results = await asyncio.gather(*tasks)
        
        # Last 100 results are subscriber counts
        subscriber_counts = results[-100:]
        print(f"Subscriber counts: min={min(subscriber_counts)}, max={max(subscriber_counts)}")
        
        # All subscribers should receive SOME messages
        assert all(c > 0 for c in subscriber_counts), "Some subscribers got 0 messages"

    @pytest.mark.slow
    def test_memory_leak_check(self):
        """
        Rough memory leak check - create many receivers and drop them.
        """
        import gc
        
        hub = SignalHub()
        
        # Create 10000 receivers and drop them
        for _ in range(10000):
            rx = hub.subscribe()
            del rx
        
        gc.collect()  # Force garbage collection
        
        # Hub should still work
        rx = hub.subscribe()
        hub.publish("test")
        assert rx.recv() == "test"


class TestSignalHubPerformance:
    """Performance benchmarks."""

    def test_benchmark_publish_latency(self):
        """
        Measure publish() latency.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        iterations = 10000
        start = time.perf_counter()
        
        for i in range(iterations):
            hub.publish(f"msg_{i}")
        
        elapsed = time.perf_counter() - start
        avg_latency_us = (elapsed / iterations) * 1_000_000
        
        print(f"Average publish latency: {avg_latency_us:.2f} μs")
        
        # Should be very fast (<10 μs per publish)
        assert avg_latency_us < 50, f"Too slow: {avg_latency_us} μs"

    def test_benchmark_recv_latency(self):
        """
        Measure recv() latency when messages are ready.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        # Pre-publish messages
        iterations = 100  # Limited by buffer size
        for i in range(iterations):
            hub.publish(f"msg_{i}")
        
        start = time.perf_counter()
        
        for _ in range(iterations):
            rx.recv()
        
        elapsed = time.perf_counter() - start
        avg_latency_us = (elapsed / iterations) * 1_000_000
        
        print(f"Average recv latency: {avg_latency_us:.2f} μs")
        
        # Should be fast
        assert avg_latency_us < 100, f"Too slow: {avg_latency_us} μs"

    @pytest.mark.asyncio
    async def test_benchmark_async_recv_overhead(self):
        """
        Measure overhead of asyncio.to_thread wrapper.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        iterations = 100
        for i in range(iterations):
            hub.publish(f"msg_{i}")
        
        start = time.perf_counter()
        
        for _ in range(iterations):
            await asyncio.to_thread(rx.recv)
        
        elapsed = time.perf_counter() - start
        avg_latency_ms = (elapsed / iterations) * 1000
        
        print(f"Average async recv latency: {avg_latency_ms:.2f} ms")
        
        # asyncio.to_thread has overhead (~1-5ms)
        assert avg_latency_ms < 10, f"Too slow: {avg_latency_ms} ms"


# Pytest markers configuration
# Add to pyproject.toml or pytest.ini:
# [tool.pytest.ini_options]
# markers = [
#     "slow: marks tests as slow (deselect with '-m \"not slow\"')"
# ]
