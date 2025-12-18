
import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from theus.config import AuditRecipe, ProcessRecipe, RuleSpec
from theus.audit import ContextAuditor, AuditInterlockError, AuditWarning
from theus.engine import POPEngine, BaseSystemContext

# --- MOCK CONTEXT ---
@dataclass
class MockUser:
    age: int = 20
    name: str = "Test"

@dataclass
class MockGlobal:
    pass

@dataclass
class MockDomain:
    user: MockUser = field(default_factory=MockUser)

@dataclass
class MockSystemContext(BaseSystemContext):
    domain_ctx: MockDomain = field(default_factory=MockDomain)

import sys
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
print("DEBUG: sys.path[0] =", sys.path[0])
import theus.audit
print("DEBUG: theus.audit file =", theus.audit.__file__)

class TestIndustrialAudit(unittest.TestCase):
    def setUp(self):
        # 1. Setup Context
        self.sys_ctx = MockSystemContext(global_ctx=MockGlobal())
        
        # 2. Setup V2 Engine with Recipe
        # Rule: process_test's input 'domain_ctx.user.age' must be >= 18 (Level S)
        # Rule: process_test's output 'domain_ctx.user.age' must be <= 100 (Level A, Thresh=2)
        
        self.recipe = AuditRecipe(definitions={
            "process_test": ProcessRecipe(
                process_name="process_test",
                input_rules=[
                    RuleSpec(target_field="domain_ctx.user.age", condition="min", value=18, level="S")
                ],
                output_rules=[
                    RuleSpec(target_field="domain_ctx.user.age", condition="max", value=100, level="A", threshold=2)
                ]
            )
        })
        
        self.engine = POPEngine(self.sys_ctx, audit_recipe=self.recipe)
        
        # Register a dummy process
        def dummy_process(ctx):
            # Simulate mutation
            ctx.domain_ctx.user.age = 150 # Violation of Output Rule
            return "DONE"
        dummy_process._pop_contract = MagicMock()
        # Guard strips '_ctx', so 'domain_ctx.user' becomes 'domain.user'
        dummy_process._pop_contract.inputs = ["domain.user"] 
        dummy_process._pop_contract.outputs = ["domain.user"]
        dummy_process._pop_contract.errors = []
        
        self.engine.register_process("process_test", dummy_process)

    def test_interlock_level_s(self):
        """Verify Level S stops execution immediately."""
        # Set invalid state for the context auditor to pick up
        self.sys_ctx.domain_ctx.user.age = 10 
        try:
            # age is 10, min 18 -> Violated
            self.engine.auditor.audit_input("process_test", self.sys_ctx)
            self.fail("Level S did not raise InterlockError")
        except AuditInterlockError as e:
            print(f"\n[TEST S] Caught Expected Interlock: {e}")

    def test_level_i_and_throttling(self):
        """Verify Level I ignores and Level C throttles."""
        # 1. Setup 'I' rule
        i_rule = RuleSpec(target_field="domain.user.age", condition="max", value=5, level="I")
        
        # 2. Check 'I' - Should pass silently even though 10 > 5
        self.engine.auditor.policy.evaluate(i_rule, 10, "test:idx")
        print("\n[TEST I] Level I passed silently.")

        # 3. Check 'C' Throttling
        c_rule = RuleSpec(target_field="domain.user.age", condition="max", value=5, level="C")
        tracker_key = "test:throttle"
        
        print("[TEST C] Testing Throttling (Simulating 15 violations)...")
        # Run 15 times
        for i in range(15):
             # We can't easily capture logs in unittest without capturing handler, 
             # but we can verify no exception is raised and code runs fast.
             self.engine.auditor.policy.evaluate(c_rule, 10, tracker_key)
        
        # Verify count in tracker
        count = self.engine.auditor.tracker._states[tracker_key].count
        self.assertEqual(count, 15)
        print(f"[TEST C] Tracker recorded {count} violations correctly.")

    def test_output_violation_A_threshold(self):
        """Test Level A Output Violation (Threshold logic)"""
        # 1. Valid Input
        self.sys_ctx.domain_ctx.user.age = 20
        
        # 2. Run 1st time -> Warning (Threshold not reached)
        # We need to mock logger to verify warning, but for simple test let's rely on NOT RAISING exception
        try:
            self.engine.run_process("process_test")
            print("\n[TEST A] Run 1: Violated but allowed (Warning).")
        except AuditInterlockError:
            self.fail("Run 1 should trigger Warning, not Interlock")
            
        # 3. Valid Input Reset (because transaction committed the invalid 150)
        self.sys_ctx.domain_ctx.user.age = 20
        
        # 4. Run 2nd time -> Warning
        try:
            self.engine.run_process("process_test")
            print("[TEST A] Run 2: Violated but allowed (Warning).")
        except AuditInterlockError:
            self.fail("Run 2 should trigger Warning, not Interlock")

        # 5. Valid Input Reset
        self.sys_ctx.domain_ctx.user.age = 20

        # 6. Run 3rd time -> Warning (Threshold=2, so >2 violates? Or >=2?)
        # Implementation: count > limit. Limit=2. 
        # Run 3 -> count=3 -> Interlock.
        
        print("[TEST A] Run 3: Expecting Interlock...")
        with self.assertRaises(AuditInterlockError):
            self.engine.run_process("process_test")
        print("[TEST A] Success: Interlock triggered on 3rd violation.")

if __name__ == '__main__':
    unittest.main()
