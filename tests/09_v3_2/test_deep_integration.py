import asyncio

import pytest
from pydantic import BaseModel

from theus import SchemaViolationError, TheusEngine, process


# Mock Process
@process(outputs=[])
def signal_emitter(ctx):
    # This should trigger Transaction -> append to pending_signal -> State.update -> SignalHub.publish
    ctx.signal.status = "active"
    ctx.signal.progress = "50%"


@pytest.mark.asyncio
async def test_deep_signal_integration():
    """
    Verify that updating ctx.signal inside a process publishes events to the shared SignalHub.
    """
    engine = TheusEngine()

    # Access the Hub via State
    hub = engine.state.signal
    print(f"SignalHub: {hub}")

    # 1. Subscribe BEFORE running
    receiver = hub.subscribe()

    # 2. Run Process (Sync wrapper around engine execution)
    # We use execute_process_async or just rely on standard engine flow
    # Since we don't have full workflow setup in this test, we might mock it or assume simple execution

    # For this test, we need to mimic what execute_workflow does:
    # Open Transaction -> Run Func -> Commit -> Close Transaction

    # Manually run transaction to simulate engine behavior
    with engine.transaction() as txn:
        # Create context
        # We can't easily create ProcessContext from here without internal API
        # So we use the engine's public API to run a named process?
        # TheusEngine doesn't expose 'execute_process' publicly easily without name/registry

        # Let's try simulating the update that happens inside a process
        # A process does: txn.update(signal={'status': 'active'})
        txn.update(signal={"status": "active"})
        txn.update(signal={"progress": "50%"})

        # Exiting context commits to State -> Publishes to Hub

    print("Transaction committed.")

    # 3. Receive Events
    # We expect 2 messages: "status:active" and "progress:50%"
    # Messages order depends on update calls.

    # Helper to read with timeout
    async def read_msg():
        # receiver.recv is blocking, run in thread
        return await asyncio.to_thread(receiver.recv)

    msg1 = await asyncio.wait_for(read_msg(), timeout=1.0)
    print(f"Received 1: {msg1}")
    assert msg1 == "status:active"

    msg2 = await asyncio.wait_for(read_msg(), timeout=1.0)
    print(f"Received 2: {msg2}")
    assert msg2 == "progress:50%"

    print("Deep Integration Verified!")


@pytest.mark.asyncio
async def test_signal_data_consistency():
    """
    INC-023 regression guard: subscriber sees committed data at the moment of signal receipt.

    Flow: commit_state() → engine.state updated → publish_signals() → subscriber wakes.
    If the order is inverted (publish before commit), seen_data["data_counter"] will be 0.
    """
    engine = TheusEngine()

    # Pre-seed so we have a known starting value
    with engine.transaction() as txn:
        txn.update(data={"data_counter": 0})

    hub = engine.state.signal
    receiver = hub.subscribe()

    seen_data: dict = {}

    def blocking_recv_and_capture():
        msg = receiver.recv()  # blocks until signal arrives
        # Capture state AT the moment signal wakes this thread.
        # If publish_signals() fires before commit_state() (regression),
        # engine.state.data["data_counter"] would still be 0 here.
        seen_data["data_counter"] = engine.state.data.get("data_counter")
        return msg

    # Create task so the thread starts immediately on next event loop iteration
    recv_task = asyncio.create_task(asyncio.to_thread(blocking_recv_and_capture))
    await asyncio.sleep(0.1)  # allow thread to start and block on recv()

    # Commit data + signal; publish_signals() runs AFTER commit_state()
    with engine.transaction() as txn:
        txn.update(data={"data_counter": 99}, signal={"ready": "true"})

    msg = await asyncio.wait_for(recv_task, timeout=2.0)
    assert msg == "ready:true"
    assert seen_data["data_counter"] == 99, (
        "INC-023 regression: signal fired before data was committed to engine.state"
    )


@pytest.mark.asyncio
async def test_schema_fail_no_signal():
    """
    INC-023: schema validation failure → no signal published (no orphaned event).

    State.update() populates last_signals (Flux latch) but does NOT publish.
    publish_signals() is called AFTER commit_state(). If commit_state() raises
    SchemaViolationError, publish_signals() is never reached → subscriber gets nothing.
    """

    class _Schema(BaseModel):
        data_status: str  # strict: must be str

    engine = TheusEngine()
    engine.set_schema(_Schema)

    hub = engine.state.signal
    receiver = hub.subscribe()

    with pytest.raises(SchemaViolationError):
        with engine.transaction() as txn:
            txn.update(
                data={"data_status": 123},       # int violates str schema
                signal={"event": "should_not_fire"},
            )

    # Subscriber must receive nothing — timeout is the passing condition
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(receiver.recv_async(), timeout=0.2)


@pytest.mark.asyncio
async def test_cas_retry_signal_exactly_once():
    """
    INC-023: CAS retry on version conflict → signal published exactly once, not N times.

    Before the fix, State.update() called signal.publish() on every CAS attempt
    (including failed retries), causing N duplicate events for 1 logical commit.
    After the fix, publish_signals() is only called after the successful commit.
    """
    engine = TheusEngine(strict_cas=True)

    # Capture stale version before bumping
    stale_version = engine.state.version  # 0

    # Bump version (no signal) so stale_version is now outdated
    with engine.transaction() as txn:
        txn.update(data={"counter": 0})
    # engine.state.version is now 1

    hub = engine.state.signal
    receiver = hub.subscribe()

    # Attempt 1: stale version → strict CAS rejects; publish_signals() NOT reached
    with pytest.raises(Exception):
        engine.compare_and_swap(
            stale_version,
            data={"counter": 99},
            heavy=None,
            signal={"done": "true"},
        )

    # Attempt 2: correct version → CAS succeeds; publish_signals() called once
    engine.compare_and_swap(
        engine.state.version,
        data={"counter": 99},
        heavy=None,
        signal={"done": "true"},
    )

    # Should receive exactly 1 signal
    msg = await asyncio.wait_for(receiver.recv_async(), timeout=1.0)
    assert msg == "done:true"

    # No duplicate from the failed attempt — timeout is the passing condition
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(receiver.recv_async(), timeout=0.1)
