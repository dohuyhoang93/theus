
import unittest
from dataclasses import dataclass, field
from theus.engine import TheusEngine
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext
from theus import process

# --- Mock Context ---
@dataclass
class MockUser:
    name: str = "TestUser"
    balance: int = 100

@dataclass
class MockDomain(BaseDomainContext):
    user: MockUser = field(default_factory=MockUser)
    temp_data: str = ""

@dataclass
class MockContext(BaseSystemContext):
    domain_ctx: MockDomain = field(default_factory=MockDomain)

# --- Mock Processes ---
@process(inputs=['domain_ctx.user'], outputs=['domain_ctx.user.balance'])
def step_1(ctx):
    ctx.domain_ctx.user.balance += 50 # 150

@process(inputs=['domain_ctx.user'], outputs=['domain_ctx.user.balance'], errors=['ValueError'])
def step_2_crash(ctx):
    ctx.domain_ctx.user.balance = 0 # Try to wipe balance
    raise ValueError("Simulated Crash")

@process(inputs=['domain_ctx.user'], outputs=[])
def step_3_read(ctx):
    pass # Just to ensure we can continue

class TestWorkflowV2(unittest.TestCase):
    def setUp(self):
        self.ctx = MockContext(
            global_ctx=BaseGlobalContext(),
            domain_ctx=MockDomain()
        )
        self.engine = TheusEngine(self.ctx)
        self.engine.register_process("step_1", step_1)
        self.engine.register_process("step_2_crash", step_2_crash)
        self.engine.register_process("step_3_read", step_3_read)

    def test_linear_execution(self):
        """Verify A -> B execution and state update."""
        workflow_steps = ["step_1"] # Linear
        
        self.engine.run_process("step_1") 
        # Note: Engine.execute_workflow logic is simple iteration in V2 MVP
        # We manually call run_process to simulate Engine loop or assume engine has execute_workflow
        
        self.assertEqual(self.ctx.domain_ctx.user.balance, 150)
        print("[TEST WORKFLOW] Linear Step Success.")

    def test_transaction_rollback(self):
        """Verify that a crash in Process DOES NOT mutate the real context."""
        initial_balance = self.ctx.domain_ctx.user.balance # 100
        
        try:
            self.engine.run_process("step_2_crash")
        except ValueError:
            pass # Expected
        
        # Check if rollback happened
        self.assertEqual(self.ctx.domain_ctx.user.balance, initial_balance)
        self.assertNotEqual(self.ctx.domain_ctx.user.balance, 0)
        print("[TEST WORKFLOW] Rollback Success. Balance preserved.")

if __name__ == '__main__':
    unittest.main()
