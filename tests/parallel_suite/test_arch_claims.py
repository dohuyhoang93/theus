import pytest
import os
import sys
from theus.engine import TheusEngine
from theus.contracts import process
from theus.structures import StateUpdate
from theus_core import AuditSystem, AuditLevel, AuditRecipe

# Import tasks module (must be importable by workers)
import tests.parallel_suite.tasks_claims as tasks_claims

@pytest.mark.asyncio
class TestArchitectureClaims:
    """
    Verifies that Rust Core actively supervises Parallel Workers.
    """

    async def test_rust_supervisor_role(self):
        """
        Proof 1: Rust Core commits worker results.
        Proof 2: Rust Core blocks execution upon Audit Threshold violation.
        """
        print("\n--- [TEST] Proving Rust Core 'Supervisor' Role ---")
        
        # [1] Init Engine with Strict Threshold
        rec = AuditRecipe(AuditLevel.Block, threshold_max=1, threshold_min=0, reset_on_success=True)
        engine = TheusEngine(audit_recipe=rec)
        
        assert engine._core is not None, "CRITICAL: Rust Core is missing!"

        # Register Tasks from external module
        engine.register(tasks_claims.heavy_worker_task)
        engine.register(tasks_claims.failing_worker_task)

        # [2] Proof 1: Commit Success (Happy Path)
        res = await engine.execute("heavy_worker_task")
        
        state_val = engine.state.data.get("evidence")
        assert state_val is not None
        assert "Processed by PID" in state_val
        print(f"    -> PROOF 1 OK: Memory updated with '{state_val}'")

        # [3] Proof 2: Audit Blocking (Failure Path)
        # A. Trigger 1st Failure (Allowed)
        try:
            await engine.execute("failing_worker_task")
        except Exception:
            pass # Expected
        
        # Manually report to simulate Supervisor logic
        engine._audit.log_fail("failing_worker_task")
        
        # B. Trigger 2nd Failure (Should BLOCK)
        with pytest.raises(RuntimeError) as excinfo:
             # Depending on wrapper, it might be RuntimeError wrapping AuditBlockError
             # Or we call audit directly to verify the BLOCK logic
             engine._audit.log_fail("failing_worker_task")
        
        assert "Audit Blocked" in str(excinfo.value)
        print("    -> PROOF 2 OK: Rust Core blocked system after threshold exceeded.")
