import asyncio
import time
import json
from theus.contracts import process
from src.context import DemoSystemContext

# --- ASYNC JOB LOGIC ---
async def heavy_async_job(duration: float):
    """Simulates I/O wait (e.g., API call)."""
    print(f"    [Background] Job sleeping for {duration}s...")
    await asyncio.sleep(duration)
    print("    [Background] Job woke up!")
    return f"Job Done at {time.time()}"

# --- PROCESSES ---


# Ephemeral Registry (Not persisted in State)
_TASK_REGISTRY = {}

@process(
    inputs=['domain.active_tasks'],
    outputs=['domain.active_tasks'],
    side_effects=['spawns_async_task']
)
async def p_spawn_background_job(ctx: DemoSystemContext):
    """
    Spawns background task.
    Returns StateUpdate to 'active_tasks'.
    """
    print("[Process] Spawning background job...")
    
    active_tasks = ctx.domain.active_tasks
    
    # Logic
    task = asyncio.create_task(heavy_async_job(2.0))
    job_id = "job_1"
    
    # Store Task in Ephemeral Registry
    _TASK_REGISTRY[job_id] = task
    
    # Clone & Modify (Immutable Pattern)
    new_tasks = active_tasks.copy()
    new_tasks[job_id] = "RUNNING"
    
    print("[Process] Job spawned. Returning StateUpdate.")
    return new_tasks 


@process(
    inputs=['domain.sync_ops_count'],
    outputs=['domain.sync_ops_count'],
    side_effects=['cpu_work']
)
def p_do_sync_work(ctx: DemoSystemContext):
    """
    Simulates CPU work.
    Returns incremented counter.
    """
    print("[Process] Doing Synchronous Work (Blocking)...")
    time.sleep(0.5) 
    
    val = ctx.domain.sync_ops_count
    new_val = val + 1
    
    print("[Process] Sync Work Done. Returning New Value.")
    return new_val


@process(
    inputs=['domain.active_tasks'],
    outputs=['domain.async_job_result', 'domain.active_tasks'],
    side_effects=['awaits_task']
)
async def p_await_job(ctx: DemoSystemContext):
    """
    Await task.
    Returns (result, updated_tasks_map).
    """
    active_tasks = ctx.domain.active_tasks
    job_status = active_tasks.get('job_1')
    
    if job_status == "RUNNING":
        task = _TASK_REGISTRY.get('job_1')
        if task:
            print("[Process] Joining background job...")
            result = await task
            print(f"[Process] Joined. Result: {result}")
            
            # Cleanup
            if 'job_1' in _TASK_REGISTRY:
                del _TASK_REGISTRY['job_1']
            
            new_tasks = active_tasks.copy()
            if 'job_1' in new_tasks:
                del new_tasks['job_1']
                
            return result, new_tasks
        else:
             print("[Process] Task object missing in registry!")
             return None, active_tasks
    else:
        print("[Process] No job to join!")
        return None, active_tasks


# --- OUTBOX LOGIC ---

@process(
    inputs=['domain.async_job_result', 'domain.outbox_queue'],
    outputs=['domain.async_job_result', 'domain.outbox_queue'], 
    side_effects=['pure_state_update']
)
def p_prepare_outbox_event(ctx: DemoSystemContext):
    try:
        from theus_core import OutboxMsg
    except ImportError:
        from theus.contracts import OutboxMsg
    
    res = ctx.domain.async_job_result
    current_queue = ctx.domain.outbox_queue
    
    payload = {"result": res, "timestamp": time.time()}
    json_payload = json.dumps(payload)
    msg = OutboxMsg(topic="JOB_COMPLETED", payload=json_payload)
    
    new_queue = list(current_queue)
    new_queue.append(msg)
    
    print(f"[Process] Event '{msg.topic}' added to State Queue.")
    new_status = f"{res} (Outbox Queued)"
    
    return new_status, new_queue

@process(
    inputs=[],
    outputs=[],
    side_effects=['logging']
)
def p_log_blindness(ctx: DemoSystemContext):
    print("\n[!!!] SIGNAL BLINDNESS DETECTED: cmd_start_outbox was ignored by Flux!")
    return None

@process(inputs=[], outputs=[], side_effects=['logging'])
def p_log_success(ctx: DemoSystemContext):
    print("\n[OK] SIGNAL RECEIVED BY FLUX: cmd_start_outbox detected!")
    return None
