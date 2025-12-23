import sys
import os
import pytest
from unittest.mock import MagicMock

# Add project root to path
# Adjust path since we are in theus/tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import theus
print(f"DEBUG: Loaded 'theus' from: {theus.__file__}")

from theus.config import AuditRecipe, ProcessRecipe, RuleSpec
from theus.audit import AuditPolicy, ContextAuditor

def test_audit_input_kwargs():
    print("\n=== TESTING AUDIT INPUT KWARGS ===")
    
    # 1. Define Recipe targeting a kwarg 'agent_id'
    recipe = AuditRecipe(definitions={
        "p_kwargs": ProcessRecipe(
            process_name="p_kwargs",
            input_rules=[
                RuleSpec(
                    target_field="agent_id", # This is a kwarg, not in ctx
                    condition="min",
                    value=0,
                    level="C"
                )
            ]
        )
    })
    
    auditor = ContextAuditor(recipe)
    
    # Mock Context (Empty)
    class Ctx: pass
    ctx = Ctx()
    
    # CASE 1: Valid Input (agent_id=1 >= 0)
    print("Test 1: Valid Input (agent_id=1)...")
    auditor.audit_input("p_kwargs", ctx, input_args={"agent_id": 1})
    
    # Check Violations History
    violations = auditor.policy.tracker.violations.get("p_kwargs", [])
    if len(violations) == 0:
        print("   -> PASS (No Violation)")
    else:
        print("   -> FAIL (Violation Recorded)")
        sys.exit(1)
    
    # Test 2: Invalid Input (agent_id=-1)
    print("Test 2: Invalid Input (agent_id=-1)...")
    auditor.audit_input("p_kwargs", ctx, input_args={"agent_id": -1})
    
    # Check Violations History
    violations = auditor.policy.tracker.violations.get("p_kwargs", [])
    print(f"   Violations recorded: {len(violations)}")
    
    if len(violations) > 0:
        print("   -> PASS (Violation Recorded in History)")
        # Verify content
        v = violations[-1]
        print(f"      Last Violation: {v.rule.target_field}={v.actual_value}")
        if v.actual_value != -1:
             print("      -> FAIL (Wrong value recorded)")
             sys.exit(1)
    else:
        print("   -> FAIL (No Violation History)")
        sys.exit(1)

    # CASE 3: Missing Input
    print("Test 3: Missing Input...")
    try:
        auditor.audit_input("p_kwargs", ctx, input_args={})
        print("   -> PASS (Graceful skip)")
    except Exception as e:
        print(f"   -> FAIL (Crashed: {e})")
        sys.exit(1)

if __name__ == "__main__":
    test_audit_input_kwargs()
