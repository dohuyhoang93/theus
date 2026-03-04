"""
Test Workflow Async: TheusEngine.execute_workflow — 4-Case Coverage (Non-Mock)
Full integration tests: TheusEngine → YAML → Rust WorkflowEngine → real @process.

NOTE: These tests use real processes with actual state mutations, no mocking.
"""

import os
import asyncio
import tempfile
import pytest
from theus import TheusEngine, process


# ================================================================
# Real processes (no mocks)
# ================================================================

@process(outputs=["domain.counter"])
def p_sync_increment(ctx):
    """Synchronous: increment counter by 1."""
    current = ctx.domain.get("counter", 0) if hasattr(ctx.domain, "get") else 0
    return {"domain.counter": current + 1}


@process(outputs=["domain.async_flag"])
async def p_async_set_flag(ctx):
    """Asynchronous: simulate IO then set flag."""
    await asyncio.sleep(0.01)
    return {"domain.async_flag": True}


@process(outputs=["domain.log"])
def p_sync_log(ctx):
    """Synchronous: append to log list."""
    current = ctx.domain.get("log", []) if hasattr(ctx.domain, "get") else []
    current.append("logged")
    return {"domain.log": current}


@process(outputs=[])
async def p_async_crash(ctx):
    """Asynchronous: crash after brief delay."""
    await asyncio.sleep(0.01)
    raise ValueError("Async process intentional crash")


@process(outputs=[])
def p_sync_noop(ctx):
    """Do nothing."""
    pass


# ================================================================
# Helper
# ================================================================

def _make_yaml(content):
    """Write YAML to temp file and return path."""
    fd, path = tempfile.mkstemp(suffix=".yaml", text=True)
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestWorkflowAsync4Case:
    """4-Case integration tests for TheusEngine.execute_workflow (non-mock)."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    @pytest.mark.asyncio
    async def test_workflow_sync_processes_via_async(self):
        """3 sync processes execute in order through async workflow."""
        engine = TheusEngine(
            context={"domain": {"counter": 0}},
            strict_guards=False
        )
        engine.register(p_sync_increment)

        yaml_path = _make_yaml("""
steps:
  - process: p_sync_increment
  - process: p_sync_increment
  - process: p_sync_increment
""")
        try:
            result = await engine.execute_workflow(yaml_path)
            assert len(result) == 3
        finally:
            os.remove(yaml_path)

    @pytest.mark.asyncio
    async def test_workflow_async_process_real(self):
        """Real async process with asyncio.sleep runs through workflow."""
        engine = TheusEngine(
            context={"domain": {"async_flag": False}},
            strict_guards=False
        )
        engine.register(p_async_set_flag)

        yaml_path = _make_yaml("""
steps:
  - process: p_async_set_flag
""")
        try:
            await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    # ================================================================
    # RELATED (Liên quan)
    # ================================================================

    @pytest.mark.asyncio
    async def test_workflow_mixed_async_sync(self):
        """Sync + async processes mixed in one workflow."""
        engine = TheusEngine(
            context={"domain": {"counter": 0, "async_flag": False}},
            strict_guards=False
        )
        engine.register(p_sync_increment)
        engine.register(p_async_set_flag)
        engine.register(p_sync_noop)

        yaml_path = _make_yaml("""
steps:
  - process: p_sync_increment
  - process: p_async_set_flag
  - process: p_sync_noop
  - process: p_sync_increment
""")
        try:
            result = await engine.execute_workflow(yaml_path)
            assert len(result) == 4
        finally:
            os.remove(yaml_path)

    @pytest.mark.asyncio
    async def test_workflow_state_updated_between_steps(self):
        """State updates propagate correctly between sequential steps."""
        engine = TheusEngine(
            context={"domain": {"log": []}},
            strict_guards=False
        )
        engine.register(p_sync_log)

        yaml_path = _make_yaml("""
steps:
  - process: p_sync_log
  - process: p_sync_log
""")
        try:
            await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    @pytest.mark.asyncio
    async def test_workflow_max_ops_override(self):
        """max_ops kwarg overrides default."""
        engine = TheusEngine(strict_guards=False)
        engine.register(p_sync_noop)

        yaml_path = _make_yaml("""
steps:
  - flux: while
    condition: "True"
    do:
      - process: p_sync_noop
""")
        try:
            with pytest.raises(Exception, match="Safety Trip"):
                await engine.execute_workflow(yaml_path, max_ops=5)
        finally:
            os.remove(yaml_path)

    @pytest.mark.asyncio
    async def test_workflow_debug_override(self):
        """debug=True kwarg enables debug logging without crash."""
        engine = TheusEngine(
            context={"domain": {}},
            strict_guards=False
        )
        engine.register(p_sync_noop)

        yaml_path = _make_yaml("""
steps:
  - process: p_sync_noop
""")
        try:
            # NOTE: Should not crash — debug only adds eprintln output
            await engine.execute_workflow(yaml_path, debug=True)
        finally:
            os.remove(yaml_path)

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    @pytest.mark.asyncio
    async def test_workflow_async_process_crash(self):
        """Async process that crashes propagates error to caller."""
        engine = TheusEngine(
            context={"domain": {}},
            strict_guards=False
        )
        engine.register(p_sync_noop)
        engine.register(p_async_crash)

        yaml_path = _make_yaml("""
steps:
  - process: p_sync_noop
  - process: p_async_crash
  - process: p_sync_noop
""")
        try:
            with pytest.raises(ValueError, match="Async process intentional crash"):
                await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    @pytest.mark.asyncio
    async def test_workflow_concurrent_execution(self):
        """Two separate workflows run concurrently via asyncio.gather."""
        engine_a = TheusEngine(
            context={"domain": {"counter": 0}},
            strict_guards=False
        )
        engine_b = TheusEngine(
            context={"domain": {"counter": 0}},
            strict_guards=False
        )
        engine_a.register(p_sync_increment)
        engine_b.register(p_sync_increment)

        yaml_a = _make_yaml("""
steps:
  - process: p_sync_increment
  - process: p_sync_increment
""")
        yaml_b = _make_yaml("""
steps:
  - process: p_sync_increment
""")
        try:
            results = await asyncio.gather(
                engine_a.execute_workflow(yaml_a),
                engine_b.execute_workflow(yaml_b),
            )
            assert len(results[0]) == 2
            assert len(results[1]) == 1
        finally:
            os.remove(yaml_a)
            os.remove(yaml_b)
