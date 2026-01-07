import unittest
from theus.config import RuleSpec, ProcessRecipe, AuditRecipe
from theus.engine import TheusEngine
from theus.audit import AuditBlockError
from dataclasses import dataclass

from typing import Any

@dataclass
class MockDomain:
    score: int = 100

@dataclass
class MockContext:
    domain_ctx: MockDomain
    global_ctx: Any = None 

class TestAuditTraceability(unittest.TestCase):
    def test_custom_message(self):
        ctx = MockContext(domain_ctx=MockDomain())
        
        # Define Rule
        proc_def = ProcessRecipe(
            process_name="test_msg",
            output_rules=[
                RuleSpec(
                    target_field="domain_ctx.score",
                    condition="min",
                    value=200, 
                    level="B",
                    max_threshold=1,
                    reset_on_success=True,
                    message="Score must be high enough to pass!"
                )
            ]
        )
        
        recipe = AuditRecipe(definitions={"test_msg": proc_def})
        engine = TheusEngine(ctx, audit_recipe=recipe)
        def dummy_process(c):
             # Guard expects inputs/outputs on contract
             return "ok"
             
        dummy_process._pop_contract = type('obj', (object,), {
             # We must allow outputting to score so audit runs
             'inputs': [], 
             'outputs': ['domain_ctx.score'], 
             'errors': []
        })
        
        engine.register_process("test_msg", dummy_process)
        
        print("\n[Traceability] Running process to trigger Audit Block...")
        try:
            engine.run_process("test_msg")
            self.fail("Should have blocked!")
        except Exception as e:
            print(f"Caught Type: {type(e)}")
            print(f"Caught Error: {e}")
            if isinstance(e, AuditBlockError):
                 msg = str(e)
                 self.assertIn("Score must be high enough to pass!", msg)
            else:
                 raise e

if __name__ == "__main__":
    unittest.main()
