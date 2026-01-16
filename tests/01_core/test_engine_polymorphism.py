import pytest
import asyncio
import threading
from theus.engine import TheusEngine
from theus.contracts import process

# TDD: Engine must route Sync to ThreadPool and Async to EventLoop

@process(inputs=[], outputs=[])
def sync_task(ctx):
    return threading.get_ident()

@process(inputs=[], outputs=[])
async def async_task(ctx):
    return threading.get_ident()

@pytest.mark.asyncio
async def test_engine_polymorphism():
    engine = TheusEngine()
    
    # 1. Run Async Task
    # It should run on the SAME thread as the Event Loop (Main Thread or Current Thread)
    current_thread = threading.get_ident()
    res_async = await engine.execute_process_async("async_task", async_task)
    assert res_async == current_thread, "Async task should run on Event Loop thread"
    
    # 2. Run Sync Task
    # It should run on a DIFFERENT thread (ThreadPool) to avoid blocking Loop
    res_sync = await engine.execute_process_async("sync_task", sync_task)
    assert res_sync != current_thread, "Sync task must be offloaded to ThreadPool"
