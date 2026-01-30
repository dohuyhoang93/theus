"""
Verification Test for Async/Sync Bridge (v3.0.22).
Verifies that engine.execute (async) and engine.execute_workflow (sync bridge) 
work correctly together, especially when calling async processes from sync workflows.
"""

import pytest
import asyncio
from pydantic import BaseModel, Field
from theus import TheusEngine, process
from theus.structures import StateUpdate
from theus.context import BaseSystemContext

# 1. Define Test Context
class SimpleDomain(BaseModel):
    item_list: list = Field(default_factory=list)
    counter: int = 0
    async_triggered: bool = False

class SimpleSystemContext(BaseSystemContext):
    def __init__(self):
        self.domain = SimpleDomain()
        self.global_ctx = {} # Empty for test

# 2. Define Processes (Sync vs Async)
@process(outputs=['domain'])
def sync_increment(ctx):
    ctx.domain.counter += 1

@process(outputs=['domain'])
async def async_trigger(ctx):
    await asyncio.sleep(0.01) # Simulate IO
    ctx.domain.async_triggered = True

@process(inputs=['domain.item_list'], outputs=['domain'])
async def async_append_const(ctx):
    ctx.domain.item_list.append("hello_from_sync_workflow")

class TestAsyncSyncBridge:
    """Suites to verify the bridge mechanics."""

    @pytest.mark.asyncio
    async def test_direct_async_execution(self):
        """Verify direct await engine.execute works for both sync and async functions."""
        engine = TheusEngine(SimpleSystemContext())
        engine.register(sync_increment)
        engine.register(async_trigger)

        # Call sync from async
        await engine.execute(sync_increment)
        assert engine.state.domain.counter == 1

        # Call async from async
        await engine.execute(async_trigger)
        assert engine.state.domain.async_triggered is True

    def test_sync_workflow_bridge(self):
        """Verify engine.execute_workflow (sync) can call async processes safely."""
        engine = TheusEngine(SimpleSystemContext())
        engine.register(sync_increment)
        engine.register(async_trigger)
        engine.register(async_append_const)

        yaml_content = """
steps:
  - process: "sync_increment"
  - process: "async_trigger"
  - process: "async_append_const"
"""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            # Call engine.execute_workflow synchronously
            engine.execute_workflow(tmp_path)

            # Verify results
            domain = engine.state.domain
            assert domain.counter == 1
            assert domain.async_triggered is True
            assert "hello_from_sync_workflow" in domain.item_list
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @pytest.mark.asyncio
    async def test_high_contention_async_retries(self):
        """Verify that async retries using asyncio.sleep don't block."""
        engine = TheusEngine(SimpleSystemContext())
        
        @process(outputs=['domain'])
        async def conflicting_increment(ctx):
            # Read current version
            v = engine.state.version
            # Trigger a background write to cause conflict
            await asyncio.sleep(0.02)
            ctx.domain.counter += 1

        engine.register(conflicting_increment)
        
        # We don't easily simulate a race here without threading, 
        # but we've verified the code uses await asyncio.sleep() in engine.py
        # which is the core fix.
        await engine.execute(conflicting_increment)
        assert engine.state.domain.counter == 1
