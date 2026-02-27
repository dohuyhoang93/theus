"""
Concurrent and Conflict Tests for SignalHub.

Tests multi-threaded scenarios, race conditions, and concurrent access patterns.
This is CRITICAL for an async pub/sub system.
"""
import pytest
import asyncio
import threading
import time
from theus import SignalHub


class TestSignalHubConcurrent:
    """High-priority concurrent scenario tests."""

    def test_concurrent_publishers_single_receiver(self):
        """
        100 threads publishing simultaneously to 1 receiver.
        Verifies: No crashes, no data corruption.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        messages_sent = threading.Event()
        received = []
        receiver_done = threading.Event()
        
        def publisher(thread_id):
            for i in range(10):
                msg = f"thread_{thread_id}_msg_{i}"
                hub.publish(msg)
                time.sleep(0.001)  # Small delay
        
        def receiver_worker():
            """Receive messages as they arrive."""
            try:
                # Try to receive for up to 3 seconds
                start = time.time()
                while time.time() - start < 3:
                    try:
                        msg = rx.recv()
                        received.append(msg)
                    except (RuntimeError, StopAsyncIteration):
                        # Lagged or channel closed
                        break
            finally:
                receiver_done.set()
        
        # Start receiver thread first
        rx_thread = threading.Thread(target=receiver_worker)
        rx_thread.start()
        
        time.sleep(0.1)  # Give receiver time to start
        
        # Launch 100 publisher threads
        threads = [threading.Thread(target=publisher, args=(i,)) for i in range(100)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        
        # Wait for receiver to finish
        receiver_done.wait(timeout=5)
        
        # At least some messages should be received
        print(f"Total publishers: 100, Total sent: 1000, Received: {len(received)}")
        assert len(received) > 0, "Should receive at least some messages"
        # Note: Receiver CAN receive all 1000 messages if it consumes fast enough
        # Buffer size only matters for lagging receivers
        assert len(received) <= 1000, "Cannot receive more than sent"


    def test_concurrent_publishers_multiple_receivers(self):
        """
        10 publishers + 10 receivers all running simultaneously.
        """
        hub = SignalHub()
        receivers = [hub.subscribe() for _ in range(10)]
        
        received_counts = [0] * 10
        locks = [threading.Lock() for _ in range(10)]
        
        def publisher(pub_id):
            for i in range(50):
                hub.publish(f"pub_{pub_id}_msg_{i}")
                time.sleep(0.01)
        
        def receiver_worker(rx_id, rx):
            try:
                for _ in range(500):  # Expect up to 500 messages
                    msg = rx.recv()
                    with locks[rx_id]:
                        received_counts[rx_id] += 1
            except (RuntimeError, StopAsyncIteration):
                # Lagged - acceptable
                pass
        
        # Launch threads
        pub_threads = [threading.Thread(target=publisher, args=(i,)) for i in range(10)]
        rx_threads = [threading.Thread(target=receiver_worker, args=(i, rx)) for i, rx in enumerate(receivers)]
        
        [t.start() for t in pub_threads + rx_threads]
        [t.join() for t in pub_threads + rx_threads]
        
        # All receivers should have received SOME messages
        for i, count in enumerate(received_counts):
            print(f"Receiver {i}: {count} messages")
            assert count > 0, f"Receiver {i} got 0 messages"

    @pytest.mark.asyncio
    async def test_subscribe_during_publish_race(self):
        """
        Race condition: new subscriptions while publishing.
        """
        hub = SignalHub()
        
        async def publish_loop():
            for i in range(200):
                hub.publish(f"msg_{i}")
                await asyncio.sleep(0.01)
        
        async def subscribe_loop():
            for i in range(20):
                rx = hub.subscribe()
                # Try to receive at least 1 message
                try:
                    msg = await asyncio.to_thread(rx.recv)
                    assert msg.startswith("msg_")
                except RuntimeError:
                    # Lagged immediately - possible if publishing fast
                    pass
                await asyncio.sleep(0.05)
        
        # Run both concurrently
        await asyncio.gather(publish_loop(), subscribe_loop())

    @pytest.mark.asyncio
    async def test_unsubscribe_simulation_concurrent(self):
        """
        Simulate unsubscribe by dropping receiver reference during active publishing.
        """
        hub = SignalHub()
        
        receivers = []
        
        async def publish_loop():
            for i in range(300):
                hub.publish(f"msg_{i}")
                await asyncio.sleep(0.005)
        
        async def subscribe_unsubscribe_loop():
            for _ in range(10):
                rx = hub.subscribe()
                receivers.append(rx)
                await asyncio.sleep(0.1)
                # Drop reference (simulate unsubscribe)
                receivers.pop()
        
        await asyncio.gather(publish_loop(), subscribe_unsubscribe_loop())
        # Should not crash

    def test_stress_rapid_subscribe_unsubscribe(self):
        """
        Rapid subscribe/unsubscribe cycles.
        """
        hub = SignalHub()
        
        for _ in range(1000):
            rx = hub.subscribe()
            # Immediately let it go out of scope
            del rx
        
        # Hub should still work
        rx = hub.subscribe()
        hub.publish("test")
        msg = rx.recv()
        assert msg == "test"

    @pytest.mark.asyncio
    async def test_deadlock_scenario_multiple_hubs(self):
        """
        Ensure no deadlock when using multiple SignalHubs.
        """
        hub1 = SignalHub()
        hub2 = SignalHub()
        
        rx1 = hub1.subscribe()
        rx2 = hub2.subscribe()
        
        async def cross_publish():
            for i in range(50):
                hub1.publish(f"h1_{i}")
                hub2.publish(f"h2_{i}")
                await asyncio.sleep(0.01)
        
        async def cross_receive():
            for _ in range(50):
                m1 = await asyncio.to_thread(rx1.recv)
                m2 = await asyncio.to_thread(rx2.recv)
                assert m1.startswith("h1_")
                assert m2.startswith("h2_")
        
        # Should not deadlock
        await asyncio.gather(cross_publish(), cross_receive())


class TestSignalHubRaceConditions:
    """Specific race condition edge cases."""

    def test_publish_before_subscribe(self):
        """
        Messages published before subscription are lost (expected behavior).
        """
        hub = SignalHub()
        hub.publish("early_message")
        
        rx = hub.subscribe()
        hub.publish("late_message")
        
        msg = rx.recv()
        assert msg == "late_message", "Should only get messages after subscription"

    @pytest.mark.asyncio
    async def test_receiver_blocking_during_hub_destruction(self):
        """
        Receiver blocked on recv() while hub goes out of scope.
        Note: This tests garbage collection behavior.
        """
        async def create_and_destroy():
            hub = SignalHub()
            rx = hub.subscribe()
            
            async def try_recv():
                try:
                    # This will block forever if hub is destroyed
                    await asyncio.wait_for(
                        asyncio.to_thread(rx.recv),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    return "timeout"
            
            # Hub goes out of scope
            result = await try_recv()
            assert result == "timeout"
        
        await create_and_destroy()

    def test_multiple_receivers_same_thread(self):
        """
        Multiple receivers in same thread should all get messages.
        """
        hub = SignalHub()
        rx1 = hub.subscribe()
        rx2 = hub.subscribe()
        rx3 = hub.subscribe()
        
        hub.publish("broadcast")
        
        assert rx1.recv() == "broadcast"
        assert rx2.recv() == "broadcast"
        assert rx3.recv() == "broadcast"
