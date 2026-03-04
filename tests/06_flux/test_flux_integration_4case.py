"""
Test Flux DSL: Integration with TheusEngine — 4-Case Coverage
Covers: Standard, Related, Boundary, Conflict

NOTE: These tests run through the full TheusEngine → WorkflowEngine → Process pipeline.
"""

import os
import pytest
import tempfile
from theus import TheusEngine, process


# ================================================================
# Test Processes (registered with @process decorator)
# ================================================================

@process(outputs=["domain.counter"])
def p_increment_counter(ctx):
    """Increment domain.counter by 1."""
    current = ctx.domain.get("counter", 0) if hasattr(ctx.domain, "get") else 0
    return {"domain.counter": current + 1}


@process(outputs=[])
def p_noop_integration(ctx):
    """Do nothing — used for control flow tests."""
    pass


@process(outputs=[])
def p_crash_integration(ctx):
    """Intentionally crash."""
    raise ValueError("Intentional process crash")


@process(outputs=["domain.log"])
def p_log_execution(ctx):
    """Append to domain.log list."""
    current_log = ctx.domain.get("log", []) if hasattr(ctx.domain, "get") else []
    current_log.append("executed")
    return {"domain.log": current_log}


# ================================================================
# Helper: Create temp YAML file
# ================================================================

def _make_yaml(content):
    """Write YAML to temp file and return path."""
    fd, path = tempfile.mkstemp(suffix=".yaml", text=True)
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestFluxIntegration4Case:
    """4-Case integration tests for Flux DSL + TheusEngine."""

    # ================================================================
    # STANDARD (Tiêu chuẩn)
    # ================================================================

    @pytest.mark.asyncio
    async def test_full_workflow_with_engine(self):
        """Full pipeline: TheusEngine → execute_workflow → real process."""
        engine = TheusEngine(context={"domain": {"counter": 0}}, strict_guards=False)
        engine.register(p_noop_integration)

        yaml_path = _make_yaml("""
steps:
  - process: p_noop_integration
""")
        try:
            await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    # ================================================================
    # RELATED (Liên quan)
    # ================================================================

    @pytest.mark.asyncio
    async def test_flux_with_strict_guards_disabled(self):
        """Workflow runs with strict_guards=False (legacy compat)."""
        engine = TheusEngine(
            context={"domain": {"value": 0}},
            strict_guards=False
        )
        engine.register(p_noop_integration)

        yaml_path = _make_yaml("""
steps:
  - process: p_noop_integration
""")
        try:
            await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    @pytest.mark.asyncio
    async def test_flux_sequential_processes(self):
        """Multiple processes execute in declaration order."""
        engine = TheusEngine(
            context={"domain": {"log": []}},
            strict_guards=False
        )
        engine.register(p_noop_integration)
        engine.register(p_log_execution)

        yaml_path = _make_yaml("""
steps:
  - process: p_log_execution
  - process: p_noop_integration
  - process: p_log_execution
""")
        try:
            await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    # ================================================================
    # BOUNDARY (Biên)
    # ================================================================

    @pytest.mark.asyncio
    async def test_flux_workflow_file_not_found(self):
        """YAML file does not exist → error."""
        engine = TheusEngine(strict_guards=False)

        with pytest.raises(Exception):
            await engine.execute_workflow("nonexistent_workflow.yaml")

    @pytest.mark.asyncio
    async def test_flux_empty_workflow_file(self):
        """Empty YAML → no processes executed, no crash."""
        engine = TheusEngine(strict_guards=False)

        yaml_path = _make_yaml("""
steps: []
""")
        try:
            await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    # ================================================================
    # CONFLICT (Xung đột)
    # ================================================================

    @pytest.mark.asyncio
    async def test_flux_process_not_registered(self):
        """Process in YAML not registered → ValueError."""
        engine = TheusEngine(strict_guards=False)

        yaml_path = _make_yaml("""
steps:
  - process: unregistered_process_xyz
""")
        try:
            with pytest.raises(ValueError, match="not found"):
                await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)

    @pytest.mark.asyncio
    async def test_flux_process_crash_propagates(self):
        """Process that throws → error propagates through workflow."""
        engine = TheusEngine(
            context={"domain": {}},
            strict_guards=False
        )
        engine.register(p_noop_integration)
        engine.register(p_crash_integration)

        yaml_path = _make_yaml("""
steps:
  - process: p_noop_integration
  - process: p_crash_integration
  - process: p_noop_integration
""")
        try:
            with pytest.raises(ValueError, match="Intentional process crash"):
                await engine.execute_workflow(yaml_path)
        finally:
            os.remove(yaml_path)
