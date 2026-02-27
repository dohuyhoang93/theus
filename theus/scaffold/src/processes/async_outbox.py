import asyncio
import time
import json
from theus.contracts import process
from src.context import DemoSystemContext


# --- ASYNC JOB LOGIC ---
async def heavy_async_job(duration: float):
    """Simulates I/O wait (e.g., API call)."""
    import logging
    log = logging.getLogger("theus.process")
    log.info(f"[Background] Job sleeping for {duration}s...")
    await asyncio.sleep(duration)
    log.info("[Background] Job woke up!")
    return f"Job Done at {time.time()}"


# --- PROCESSES ---


# Ephemeral Registry (Not persisted in State)
_TASK_REGISTRY = {}


@process(
    inputs=["tasks.active_tasks"],
    outputs=["tasks.active_tasks"],
    side_effects=["spawns_async_task"],
)
async def p_spawn_background_job(ctx: DemoSystemContext):
    """
    Spawns background task.
    Returns StateUpdate to 'active_tasks'.
    """
    ctx.log.info("[Process] Spawning background job...")

    active_tasks = ctx.tasks.active_tasks

    # Logic
    task = asyncio.create_task(heavy_async_job(2.0))
    job_id = "job_1"

    # Store Task in Ephemeral Registry
    _TASK_REGISTRY[job_id] = task

    # Clone & Modify (Immutable Pattern)
    new_tasks = active_tasks.copy()
    new_tasks[job_id] = "RUNNING"

    ctx.log.info("[Process] Job spawned. Returning StateUpdate.")
    return new_tasks


@process(
    inputs=["tasks.sync_ops_count"],
    outputs=["tasks.sync_ops_count"],
    side_effects=["cpu_work"],
)
def p_do_sync_work(ctx: DemoSystemContext):
    """
    Simulates CPU work.
    Returns incremented counter.
    """
    ctx.log.info("[Process] Doing Synchronous Work (Blocking)...")
    time.sleep(0.5)

    val = ctx.tasks.sync_ops_count
    new_val = val + 1

    ctx.log.info("[Process] Sync Work Done. Returning New Value.")
    return new_val


@process(
    inputs=["tasks.active_tasks"],
    outputs=["tasks.async_job_result", "tasks.active_tasks"],
    side_effects=["awaits_task"],
)
async def p_await_job(ctx: DemoSystemContext):
    """
    Await task.
    Returns (result, updated_tasks_map).
    """
    active_tasks = ctx.tasks.active_tasks
    job_status = active_tasks.get("job_1")

    if job_status == "RUNNING":
        task = _TASK_REGISTRY.get("job_1")
        if task:
            ctx.log.info("[Process] Joining background job...")
            result = await task
            ctx.log.info(f"[Process] Joined. Result: {result}")

            # Cleanup
            if "job_1" in _TASK_REGISTRY:
                del _TASK_REGISTRY["job_1"]

            new_tasks = active_tasks.copy()
            if "job_1" in new_tasks:
                del new_tasks["job_1"]

            return result, new_tasks
        else:
            ctx.log.warning("[Process] Task object missing in registry!")
            return None, active_tasks
    else:
        ctx.log.info("[Process] No job to join!")
        return None, active_tasks


# --- OUTBOX LOGIC ---


@process(
    inputs=["tasks.async_job_result", "tasks.log_outbox"],
    outputs=["tasks.async_job_result", "tasks.log_outbox"],
    side_effects=["pure_state_update"],
)
def p_prepare_outbox_event(ctx: DemoSystemContext):
    try:
        from theus_core import OutboxMsg
    except ImportError:
        from theus.contracts import OutboxMsg

    res = ctx.tasks.async_job_result
    current_queue = ctx.tasks.log_outbox

    payload = {"result": res, "timestamp": time.time()}
    json_payload = json.dumps(payload)
    msg = OutboxMsg(topic="JOB_COMPLETED", payload=json_payload)

    # RFC-001: Append-only pattern
    new_queue = list(current_queue)
    new_queue.append(msg)

    ctx.log.info(f"[Process] Event '{msg.topic}' added to State Queue.")
    new_status = f"{res} (Outbox Queued)"

    return new_status, new_queue


@process(inputs=[], outputs=[], side_effects=["logging"])
def p_log_blindness(ctx: DemoSystemContext):
    ctx.log.warning("SIGNAL BLINDNESS DETECTED: cmd_start_outbox was ignored by Flux!")
    return None


@process(inputs=[], outputs=[], side_effects=["logging"])
def p_log_success(ctx: DemoSystemContext):
    ctx.log.info("SIGNAL RECEIVED BY FLUX: cmd_start_outbox detected!")
    return None
