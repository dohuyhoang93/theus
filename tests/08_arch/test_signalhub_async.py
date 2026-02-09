"""Tests for recv_async() native async API."""
import pytest
import asyncio
import time
from theus import SignalHub


class TestRecvAsync:
    """Test native async recv_async() method."""
    
    @pytest.mark.asyncio
    async def test_basic_async_receive(self):
        """Basic receive with recv_async()."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("test_message")
        msg = await rx.recv_async()
        
        assert msg == "test_message"
    
    @pytest.mark.asyncio
    async def test_timeout_works(self):
        """asyncio.wait_for timeout SHOULD work with recv_async()."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        # No message published - should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(rx.recv_async(), timeout=0.5)
    
    @pytest.mark.asyncio
    async def test_multiple_sequential_receives(self):
        """Receive multiple messages sequentially."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("msg1")
        hub.publish("msg2")
        hub.publish("msg3")
        
        msg1 = await rx.recv_async()
        msg2 = await rx.recv_async()
        msg3 = await rx.recv_async()
        
        assert msg1 == "msg1"
        assert msg2 == "msg2"
        assert msg3 == "msg3"
    
    @pytest.mark.asyncio
    async def test_concurrent_async_receivers(self):
        """Multiple async receivers concurrently."""
        hub = SignalHub()
        receivers = [hub.subscribe() for _ in range(10)]
        
        async def receiver_task(rx, results, idx):
            msg = await rx.recv_async()
            results[idx] = msg
        
        results = [None] * 10
        
        # Start all receivers
        tasks = [
            asyncio.create_task(receiver_task(rx, results, i))
            for i, rx in enumerate(receivers)
        ]
        
        await asyncio.sleep(0.1)
        
        # Publish message
        hub.publish("broadcast")
        
        # Wait for all
        await asyncio.gather(*tasks)
        
        assert all(r == "broadcast" for r in results)
    
    @pytest.mark.asyncio
    async def test_lag_error_async(self):
        """Lag error raised in async context."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        # Flood
        for i in range(150):
            hub.publish(f"msg_{i}")
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Channel Lagged"):
            await rx.recv_async()
    
    @pytest.mark.asyncio
    async def test_both_apis_coexist(self):
        """Both recv() and recv_async() work on same receiver."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("msg1")
        hub.publish("msg2")
        
        # Use blocking recv via to_thread
        msg1 = await asyncio.to_thread(rx.recv)
        assert msg1 == "msg1"
        
        # Use async recv
        msg2 = await rx.recv_async()
        assert msg2 == "msg2"
    
    @pytest.mark.asyncio
    async def test_unicode_async(self):
        """Unicode messages work with recv_async()."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        test_msgs = [
            "Hello 世界",
            "🚀 Emoji test 🎉",
            "Ñoño España"
        ]
        
        for msg in test_msgs:
            hub.publish(msg)
            received = await rx.recv_async()
            assert received == msg


class TestRecvAsyncRaceConditions:
    """Test race conditions and concurrent access patterns."""
    
    @pytest.mark.asyncio
    async def test_concurrent_recv_async_same_receiver(self):
        """Two recv_async() calls on same receiver - should work sequentially."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("msg1")
        hub.publish("msg2")
        
        # Concurrent recv on SAME receiver
        results = await asyncio.gather(
            rx.recv_async(),
            rx.recv_async()
        )
        
        assert len(results) == 2
        assert set(results) == {"msg1", "msg2"}
    
    @pytest.mark.asyncio
    async def test_publish_during_recv_async(self):
        """Publish while recv_async() is waiting."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        async def delayed_publish():
            await asyncio.sleep(0.1)
            hub.publish("delayed")
        
        # Start both concurrently - recv_async() returns Future, can await directly
        msg, _ = await asyncio.gather(
            rx.recv_async(),
            delayed_publish()
        )
        
        assert msg == "delayed"
    
    @pytest.mark.asyncio
    async def test_mixed_api_concurrent(self):
        """recv() and recv_async() called concurrently on same receiver."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("msg1")
        hub.publish("msg2")
        
        # Mixed APIs - both should work
        results = await asyncio.gather(
            rx.recv_async(),
            asyncio.to_thread(rx.recv)
        )
        
        assert len(results) == 2
        assert set(results) == {"msg1", "msg2"}
    
    @pytest.mark.asyncio
    async def test_multiple_receivers_race(self):
        """Multiple receivers competing for messages on different subscriptions."""
        hub = SignalHub()
        receivers = [hub.subscribe() for _ in range(5)]
        
        async def receiver_waits(rx):
            """Wrapper to await recv_async Future."""
            return await rx.recv_async()
        
        # All receivers waiting
        tasks = [asyncio.create_task(receiver_waits(rx)) for rx in receivers]
        
        await asyncio.sleep(0.05)
        
        # Publish - all should receive (broadcast)
        hub.publish("broadcast_msg")
        
        results = await asyncio.gather(*tasks)
        
        assert all(r == "broadcast_msg" for r in results)


class TestRecvAsyncBoundary:
    """Test boundary conditions and edge cases."""
    
    @pytest.mark.asyncio
    async def test_exactly_buffer_limit(self):
        """Publish exactly 100 messages (buffer capacity)."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        # Publish exactly buffer size
        for i in range(100):
            hub.publish(f"msg_{i}")
        
        # Should receive all without lag
        for i in range(100):
            msg = await rx.recv_async()
            assert msg == f"msg_{i}"
    
    @pytest.mark.asyncio
    async def test_empty_channel_blocks(self):
        """recv_async() on empty channel blocks until message arrives."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        async def delayed_publish():
            await asyncio.sleep(0.2)
            hub.publish("late")
        
        asyncio.create_task(delayed_publish())
        
        start = time.time()
        msg = await asyncio.wait_for(rx.recv_async(), timeout=0.5)
        elapsed = time.time() - start
        
        assert msg == "late"
        assert 0.15 < elapsed < 0.35  # Blocked ~0.2s
    
    @pytest.mark.asyncio
    async def test_very_long_message(self):
        """Messages with large strings (100KB)."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        # 100KB message
        long_msg = "x" * (100 * 1024)
        hub.publish(long_msg)
        
        received = await rx.recv_async()
        assert received == long_msg
        assert len(received) == 100 * 1024
    
    @pytest.mark.asyncio
    async def test_rapid_subscribe_unsubscribe(self):
        """Rapid creation and destruction of subscriptions."""
        hub = SignalHub()
        
        # Create many short-lived subscriptions
        for _ in range(20):
            rx = hub.subscribe()
            hub.publish("test")
            msg = await rx.recv_async()
            assert msg == "test"
            del rx  # Explicit cleanup


class TestRecvAsyncIntegration:
    """Integration tests simulating production workflows."""
    
    @pytest.mark.asyncio
    async def test_event_driven_workflow(self):
        """Simulate event-driven architecture: producer → hub → consumer."""
        hub = SignalHub()
        rx = hub.subscribe()  # Subscribe first
        
        processed = []
        
        async def producer():
            """Simulate service publishing events."""
            await asyncio.sleep(0.05)  # Let consumer start first
            for i in range(10):
                hub.publish(f"event_{i}")
                await asyncio.sleep(0.01)
        
        async def consumer():
            """Simulate service consuming events."""
            for _ in range(10):
                event = await asyncio.wait_for(
                    rx.recv_async(),
                    timeout=2.0
                )
                processed.append(event)
        
        # Run both concurrently
        await asyncio.gather(producer(), consumer())
        
        assert len(processed) == 10
        assert all(f"event_{i}" in processed for i in range(10))
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Worker shutdown with timeout and cleanup."""
        hub = SignalHub()
        rx = hub.subscribe()
        shutdown = asyncio.Event()
        
        received = []
        
        async def worker():
            while not shutdown.is_set():
                try:
                    msg = await asyncio.wait_for(
                        rx.recv_async(),
                        timeout=0.1
                    )
                    received.append(msg)
                except asyncio.TimeoutError:
                    continue  # No message, check shutdown
        
        # Start worker
        worker_task = asyncio.create_task(worker())
        
        # Publish some messages
        hub.publish("msg1")
        hub.publish("msg2")
        await asyncio.sleep(0.2)
        
        # Initiate shutdown
        shutdown.set()
        
        # Wait for graceful exit
        await asyncio.wait_for(worker_task, timeout=1.0)
        
        assert "msg1" in received
        assert "msg2" in received
    
    @pytest.mark.asyncio
    async def test_error_recovery_resubscribe(self):
        """Lag error → re-subscribe → continue."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        # Cause lag
        for i in range(150):
            hub.publish(f"flood_{i}")
        
        # First recv will lag
        with pytest.raises(RuntimeError, match="Lagged"):
            await rx.recv_async()
        
        # Re-subscribe
        rx = hub.subscribe()
        
        # Publish new message
        hub.publish("recovery")
        
        # Should receive successfully
        msg = await rx.recv_async()
        assert msg == "recovery"
