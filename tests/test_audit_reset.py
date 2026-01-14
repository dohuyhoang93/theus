import sys
import os
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from theus import TheusEngine, BaseSystemContext, BaseGlobalContext, BaseDomainContext, process
from theus.config import AuditRecipe, ProcessRecipe, RuleSpec
from theus.audit import AuditBlockError

@dataclass
class MockDomain(BaseDomainContext):
    value: int = 0

@process(inputs=['domain_ctx.value'], outputs=['domain_ctx.value'])
def p_test(ctx):
    # Dummy process
    pass

class TestAuditReset(unittest.TestCase):
    def test_audit_reset_accumulation(self):
        print("\n=== TESTING AUDIT RESET (RUST ENGINE) ===")
        
        # 1. Define Recipe
        print("Scenario: value < 10 (Accumulate -> Block on 3rd)")
        recipe = AuditRecipe(definitions={
            "p_test": ProcessRecipe(
                process_name="p_test",
                input_rules=[
                    RuleSpec(
                        target_field="domain_ctx.value",
                        condition="min",
                        value=10,
                        level="B", 
                        min_threshold=0,
                        max_threshold=3, # Fail on 3rd violation
                        reset_on_success=False
                    )
                ]
            )
        })

        # 2. Setup Engine
        dom = MockDomain(value=5) # 5 < 10 -> Violation
        ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=dom)
        
        engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
        engine.register_process("p_test", p_test)
        
        # Step 1: Fail (Count 1) -> Warning
        print("Step 1 (Fail): ", end="")
        engine.run_process("p_test")
        print("OK (No Block)")
        
        # Step 2: Fail (Count 2) -> Warning
        print("Step 2 (Fail): ", end="")
        engine.run_process("p_test")
        print("OK (No Block)")
        
        # Step 3: Fail (Count 3) -> BLOCK EXCEPTION
        print("Step 3 (Fail): ", end="")
        with self.assertRaises(AuditBlockError):
            engine.run_process("p_test")
        print("OK (Caught Block Error)")
        
        # Step 4: Success Logic
        print("Step 4 (Fail Again - Cyclic Reset Check): ", end="")
        engine.run_process("p_test")
        print("OK (No Block - Reset confirmed)")

if __name__ == "__main__":
    unittest.main()
