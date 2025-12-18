import pytest
import time
import logging
import os
import yaml
from theus import POPEngine
from theus.config import ConfigFactory, AuditRecipe
from src.context import DemoSystemContext
from src.processes.chain import p_process

# Configure Logging
logging.basicConfig(level=logging.INFO)

def test_audit_input_validation():
    """
    Test Audit Input Gate.
    Rule: 'p_process' requires processed_count < 100.
    Scenario: Context has processed_count = 999.
    Expected: Engine blocks execution with AuditViolation/Interlock.
    """
    basedir = os.path.dirname(os.path.abspath(__file__))
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")
    
    # 1. Load Recipe
    if os.path.exists(audit_path):
        recipe = ConfigFactory.load_recipe(audit_path)
    else:
        pytest.fail("Audit Recipe file not found")

    sys = DemoSystemContext()
    sys.domain_ctx.processed_count = 999 # VIOLATION! > 100

    # Initialize Engine with Audit
    engine = POPEngine(sys, strict_mode=True, audit_recipe=recipe)
    engine.register_process("p_process", p_process)
    
    # 2. Execute
    print("\n[TEST] Executing p_process with processed_count=999 (Should Fail Audit)...")
    
    with pytest.raises(Exception) as excinfo:
        engine.execute_process("p_process")
    
    print(f"Exception Caught: {excinfo.value}")
    
    # 3. Verify
    # The error message from AuditPolicy: "[LEVEL S] INTERLOCK: Audit Violation: processed_count (999) failed max 100"
    assert "Audit Violation" in str(excinfo.value)
    
    print("✅ PASS: Audit correctly blocked invalid input.")

def test_audit_output_invariant():
    """
    Test Audit Output Gate.
    Rule: processed_count >= 0.
    Scenario: Process sets processed_count = -5.
    """
    from theus import process
    
    @process(inputs=['domain.processed_count'], outputs=['domain.processed_count'])
    def p_break_logic(ctx):
        ctx.domain_ctx.processed_count = -5
        return "Broken"

    # Setup
    basedir = os.path.dirname(os.path.abspath(__file__))
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    sys = DemoSystemContext()
    engine = POPEngine(sys, strict_mode=True, audit_recipe=recipe)
    engine.register_process("p_break_logic", p_break_logic)
    
    print("\n[TEST] Executing p_break_logic (Should Fail Output Audit)...")
    
    with pytest.raises(Exception) as excinfo:
        engine.execute_process("p_break_logic")
        
    print(f"Exception Caught: {excinfo.value}")
    assert "Audit Violation" in str(excinfo.value)
    
    print("✅ PASS: Audit correctly blocked invalid output.")
