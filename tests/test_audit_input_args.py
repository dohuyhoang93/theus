import sys
import os
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext
from theus.config import AuditRecipe, ProcessRecipe, RuleSpec
from theus.audit import AuditBlockError

@process(inputs=[], outputs=[])
def p_kwargs(ctx, agent_id=0):
    pass

class TestAuditInputArgs(unittest.TestCase):
    def test_audit_kwargs_violation(self):
        print("\n=== TESTING AUDIT KWARGS (RUST ENGINE) ===")
        
        # 1. Define Recipe
        recipe = AuditRecipe(definitions={
            "p_kwargs": ProcessRecipe(
                process_name="p_kwargs",
                input_rules=[
                    RuleSpec(
                        target_field="agent_id", # kwarg not in ctx, so path is just key
                        condition="min",
                        value=0,
                        level="B"
                    )
                ]
            )
        })
        
        # Use Standard Contexts
        ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=BaseDomainContext())
        
        engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
        engine.register_process("p_kwargs", p_kwargs)
        
        # Case 1: Valid
        engine.run_process("p_kwargs", agent_id=1)
        print("Case 1 (Valid): OK")
        
        # Case 2: Invalid -> Block
        with self.assertRaises(AuditBlockError):
            engine.run_process("p_kwargs", agent_id=-1)
        print("Case 2 (Invalid): Caught Block Error")

if __name__ == "__main__":
    unittest.main()
