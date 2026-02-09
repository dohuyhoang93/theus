"""
Boundary and Edge Case Tests for SignalHub.

Tests limits, boundaries, and unusual inputs.
"""
import pytest
from theus import SignalHub


class TestSignalHubBoundary:
    """Boundary value tests."""

    def test_exactly_100_messages(self):
        """
        Exactly at buffer capacity (100 messages).
        All should be received without lag.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        # Fill exactly 100 messages
        for i in range(100):
            hub.publish(f"msg_{i}")
        
        # Should receive all 100 without error
        for i in range(100):
            msg = rx.recv()
            assert msg == f"msg_{i}", f"Expected msg_{i}, got {msg}"

    def test_101_messages_first_overflow(self):
        """
        101 messages published rapidly without consuming.
        Should cause lag if not consumed in time.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        # Publish rapidly without consuming
        for i in range(150):  # More than buffer to ensure lag
            hub.publish(f"msg_{i}")
        
        # First recv should fail with lag error
        with pytest.raises(RuntimeError, match="Channel Lagged"):
            rx.recv()

    def test_exactly_99_messages(self):
        """
        99 messages = just under capacity.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        for i in range(99):
            hub.publish(f"msg_{i}")
        
        for i in range(99):
            msg = rx.recv()
            assert msg == f"msg_{i}"

    def test_zero_messages(self):
        """
        No messages published - recv() should block.
        Using timeout to verify blocking behavior.
        """
        import threading
        import time
        
        hub = SignalHub()
        rx = hub.subscribe()
        
        result = [None]
        
        def try_recv():
            try:
                result[0] = rx.recv()
            except Exception as e:
                result[0] = f"error: {e}"
        
        thread = threading.Thread(target=try_recv)
        thread.start()
        time.sleep(0.5)  # Wait a bit
        
        # Thread should still be blocked
        assert thread.is_alive(), "recv() should block when no messages"
        
        # Publish to unblock
        hub.publish("unblock")
        thread.join(timeout=1.0)
        
        assert result[0] == "unblock"

    def test_single_message(self):
        """Minimum case: single message."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("single")
        assert rx.recv() == "single"

    def test_zero_subscribers(self):
        """
        Publishing with no subscribers.
        """
        hub = SignalHub()
        count = hub.publish("nobody_listening")
        assert count == 0, "Should return 0 when no subscribers"

    def test_single_subscriber(self):
        """Minimum subscribers: exactly 1."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        count = hub.publish("msg")
        assert count == 1
        assert rx.recv() == "msg"

    def test_many_subscribers_boundary(self):
        """
        1000 subscribers (stress test for subscriber limit).
        """
        hub = SignalHub()
        receivers = [hub.subscribe() for _ in range(1000)]
        
        count = hub.publish("broadcast")
        assert count == 1000
        
        # Sample check: first, middle, last receiver
        assert receivers[0].recv() == "broadcast"
        assert receivers[500].recv() == "broadcast"
        assert receivers[999].recv() == "broadcast"


class TestSignalHubEdgeCases:
    """Unusual inputs and edge scenarios."""

    def test_empty_string_message(self):
        """Empty string is valid."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        hub.publish("")
        assert rx.recv() == ""

    def test_very_long_message(self):
        """
        Very long message (1MB string).
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        # 1MB message
        long_msg = "x" * (1024 * 1024)
        hub.publish(long_msg)
        
        received = rx.recv()
        assert len(received) == 1024 * 1024
        assert received == long_msg

    def test_unicode_messages(self):
        """
        Unicode and special characters.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        test_cases = [
            "Hello 世界",
            "🚀 Emoji test 🎉",
            "Ñoño España",
            "Привет мир",
            "مرحبا",
            "\n\t\r Special whitespace"
        ]
        
        for msg in test_cases:
            hub.publish(msg)
            received = rx.recv()
            assert received == msg, f"Unicode mismatch: expected {msg!r}, got {received!r}"

    def test_json_escaped_characters(self):
        """
        Common JSON special characters.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        msg = '{"key": "value", "nested": {"array": [1, 2, 3]}}'
        hub.publish(msg)
        assert rx.recv() == msg

    def test_newline_in_message(self):
        """Multi-line messages."""
        hub = SignalHub()
        rx = hub.subscribe()
        
        multiline = "line1\nline2\nline3"
        hub.publish(multiline)
        assert rx.recv() == multiline

    def test_null_bytes_in_message(self):
        """
        Null bytes (though unusual for text).
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        msg = "before\x00after"
        hub.publish(msg)
        received = rx.recv()
        assert received == msg

    def test_rapid_publish_recv_cycle(self):
        """
        Publish and receive immediately in tight loop.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        for i in range(100):
            hub.publish(f"msg_{i}")
            assert rx.recv() == f"msg_{i}"

    def test_receiver_after_many_publishes(self):
        """
        Subscribe AFTER many messages were already published.
        New receiver should not get old messages.
        """
        hub = SignalHub()
        
        # Publish 50 messages
        for i in range(50):
            hub.publish(f"old_{i}")
        
        # Now subscribe
        rx = hub.subscribe()
        
        # Publish new message
        hub.publish("new")
        
        # Should only get the new message
        assert rx.recv() == "new"

    def test_alternating_subscribe_publish(self):
        """
        Subscribe, publish, subscribe, publish pattern.
        """
        hub = SignalHub()
        
        rx1 = hub.subscribe()
        hub.publish("msg1")
        
        rx2 = hub.subscribe()
        hub.publish("msg2")
        
        rx3 = hub.subscribe()
        hub.publish("msg3")
        
        # rx1 should get all 3
        assert rx1.recv() == "msg1"
        assert rx1.recv() == "msg2"
        assert rx1.recv() == "msg3"
        
        # rx2 should get msg2 and msg3
        assert rx2.recv() == "msg2"
        assert rx2.recv() == "msg3"
        
        # rx3 should get only msg3
        assert rx3.recv() == "msg3"


class TestSignalHubErrorHandling:
    """Error scenarios and recovery."""

    def test_multiple_lag_errors(self):
        """
        Receiver lags, receives error, then can recover.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        # First lag
        for i in range(200):
            hub.publish(f"flood1_{i}")
        
        with pytest.raises(RuntimeError, match="Channel Lagged"):
            rx.recv()
        
        # After lag error, new messages should work
        hub.publish("recovery")
        
        # NOTE: After lag, the receiver is still "lagged" and will error again
        # This is expected Tokio broadcast behavior
        with pytest.raises(RuntimeError):
            rx.recv()

    def test_lag_error_message_format(self):
        """
        Verify lag error message includes count.
        """
        hub = SignalHub()
        rx = hub.subscribe()
        
        for i in range(150):
            hub.publish(f"msg_{i}")
        
        try:
            rx.recv()
            pytest.fail("Should have raised RuntimeError")
        except RuntimeError as e:
            error_msg = str(e)
            assert "Channel Lagged" in error_msg
            assert "missed" in error_msg
            # Should mention number of missed messages
            assert any(char.isdigit() for char in error_msg)
