import asyncio
import time
import json
from theus.contracts import process
from theus.structures import StateUpdate  # Standard V3 Update Mechanism
from context import DemoSystemContext
from database import get_connection, insert_outbox_event
from helpers import get_attr # Minimal read helper

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
    
    # Read current (Safe via helper or access)
    active_tasks = get_attr(ctx, 'domain.active_tasks', {})
    
    # Logic
    task = asyncio.create_task(heavy_async_job(2.0))
    job_id = "job_1"
    
    # Store Task in Ephemeral Registry
    _TASK_REGISTRY[job_id] = task
    
    # Store ID in Persistent State
    new_tasks = active_tasks.copy()
    new_tasks[job_id] = "RUNNING"
    
    print("[Process] Job spawned. Returning StateUpdate.")
    # Return explicit update
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
    
    val = get_attr(ctx, 'domain.sync_ops_count', 0)
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
    active_tasks = get_attr(ctx, 'domain.active_tasks', {})
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
                
            # Return Tuple matching outputs=[result, tasks]
            return result, new_tasks
        else:
             print("[Process] Task object missing in registry!")
             return None, active_tasks
    else:
        print("[Process] No job to join!")
        return None, active_tasks


# --- OUTBOX LOGIC ---

# --- OUTBOX LOGIC ---

# V3 Standard: Use Theus Built-in Outbox
# requires: from theus.contracts import OutboxMsg

# HACK: Module-level buffer to bypass Rust binding issues in Demo Environment
_EMERGENCY_OUTBOX = []

@process(
    inputs=['domain.async_job_result', 'domain.outbox_queue'],
    outputs=['domain.async_job_result', 'domain.outbox_queue'], # Permission to update Queue
    side_effects=['pure_state_update']
)
def p_prepare_outbox_event(ctx: DemoSystemContext):
    """
    Business Logic: Prepare event based on result.
    Uses Theus Immutable State Pattern (Return Data).
    """
    try:
        from theus_core import OutboxMsg
    except ImportError:
        from theus.contracts import OutboxMsg
    
    # 1. Read Inputs (Safe/Immutable)
    res = get_attr(ctx, 'domain.async_job_result')
    current_queue = get_attr(ctx, 'domain.outbox_queue', [])
    
    # 2. Logic: Create Event
    payload = {"result": res, "timestamp": time.time()}
    json_payload = json.dumps(payload)
    msg = OutboxMsg(topic="JOB_COMPLETED", payload=json_payload)
    
    # 3. Immutable Update: Return New Data
    # We append to the queue (Creating a new list)
    new_queue = list(current_queue)
    new_queue.append(msg)
    
    print(f"[Process] Event '{msg.topic}' added to State Queue.")
    
    # 4. Return Data (Signals Engine to CAS)
    new_status = f"{res} (Outbox Queued)"
    
    # We need to return MULTIPLE updates.
    # Theus V3 helper or Tuple return?
    # engine.py supports returning TUPLE mapping to outputs list.
    
    return new_status, new_queue

# p_flush_outbox REMOVED.
# Persisting to DB is now a System-Level Relay task, not a workflow step.

@process(
    inputs=[],
    outputs=[],
    side_effects=['logging']
)
def p_log_blindness(ctx: DemoSystemContext):
    """
    Logs blindness detection.
    """
    print("\n[!!!] SIGNAL BLINDNESS DETECTED: cmd_start_outbox was ignored by Flux!")
    return None

@process(inputs=[], outputs=[], side_effects=['logging'])
def p_log_success(ctx: DemoSystemContext):
    print("\n[OK] SIGNAL RECEIVED BY FLUX: cmd_start_outbox detected!")
    return None
