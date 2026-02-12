"""
Manual test for recv_async() - basic async receive.
"""
import asyncio
from theus import SignalHub


async def main():
    hub = SignalHub()
    rx = hub.subscribe()
    
    print("Test 1: Basic async receive")
    hub.publish("test_message")
    msg = await rx.recv_async()
    print(f"✅ Received: {msg}")
    assert msg == "test_message"
    
    print("\nTest 2: Timeout works")
    try:
        await asyncio.wait_for(rx.recv_async(), timeout=0.5)
        print("❌ Should have timed out")
    except asyncio.TimeoutError:
        print("✅ Timeout raised correctly")
    
    print("\nTest 3: Can be awaited multiple times")
    hub.publish("msg2")
    hub.publish("msg3")
    
    msg2 = await rx.recv_async()
    msg3 = await rx.recv_async()
    print(f"✅ Received sequentially: {msg2}, {msg3}")
    assert msg2 == "msg2" and msg3 == "msg3"
    
    print("\n✅ All manual tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
