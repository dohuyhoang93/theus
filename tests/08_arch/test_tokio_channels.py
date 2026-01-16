import pytest
import asyncio
import threading
import time
from theus import SignalHub

class TestTokioChannels:
    """
    Verifies that SignalHub (Rust + Tokio) can correctly broadcast messages 
    to Python consumers running in separate threads/loops.
    """

    def test_basic_pub_sub(self):
        hub = SignalHub()
        rx1 = hub.subscribe()
        rx2 = hub.subscribe()

        # Publish should see 2 subscribers
        count = hub.publish("hello")
        assert count == 2

    @pytest.mark.asyncio
    async def test_async_consumption(self):
        """
        Verify that we can consume messages using asyncio.to_thread wrapping the blocking recv().
        """
        hub = SignalHub()
        
        # Start a subscriber task
        async def subscriber_task(rx, name):
            msgs = []
            try:
                # We expect 3 messages
                for _ in range(3):
                    msg = await asyncio.to_thread(rx.recv)
                    msgs.append(msg)
            except Exception as e:
                msgs.append(f"Error: {e}")
            return msgs

        rx1 = hub.subscribe()
        rx2 = hub.subscribe()

        # Launch listeners
        task1 = asyncio.create_task(subscriber_task(rx1, "Sub1"))
        task2 = asyncio.create_task(subscriber_task(rx2, "Sub2"))

        # Give them a moment to be 'ready' (although broadcast holds history if buffer allows, 
        # but here they are already subscribed)
        await asyncio.sleep(0.1)

        # Publish messages
        hub.publish("msg1")
        hub.publish("msg2")
        hub.publish("msg3")

        # Wait for tasks
        res1 = await task1
        res2 = await task2

        assert res1 == ["msg1", "msg2", "msg3"]
        assert res2 == ["msg1", "msg2", "msg3"]

    def test_lagged_receiver(self):
        """
        Verify that slow receivers get an error if they lag too far behind buffer (100).
        """
        hub = SignalHub()
        rx = hub.subscribe()

        # Fill buffer beyond 100
        for i in range(300):
            hub.publish(f"flood_{i}")

        # The receiver should now be lagged
        try:
            val = rx.recv()
            print(f"DEBUG: Receiver got {val} instead of Lagged Error")
        except RuntimeError:
            return # Success
            
        pytest.fail("Did not raise RuntimeError (Channel Lagged)")
