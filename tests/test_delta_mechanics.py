import unittest
from dataclasses import dataclass, field
from typing import List, Dict
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext, ContractViolationError

# --- Domain Mock ---
@dataclass
class MockGlobal(BaseGlobalContext):
    limit: int = 10

@dataclass
class MockDomain(BaseDomainContext):
    count: int = 0
    items: List[int] = field(default_factory=list)
    cache: Dict[str, str] = field(default_factory=dict)

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

# --- Processes ---
@process(
    inputs=['domain_ctx.count'],
    outputs=['domain_ctx.count']
)
def simple_increment(ctx):
    # Valid scalar update
    ctx.domain_ctx.count += 1
    return "Incremented"

@process(
    inputs=['domain_ctx.items'],
    outputs=['domain_ctx.items']
)
def list_append(ctx):
    # Valid list update
    ctx.domain_ctx.items.append(99)
    return "Appended"

@process(
    inputs=['domain_ctx.count', 'domain_ctx.items'],
    outputs=['domain_ctx.count', 'domain_ctx.items'],
    errors=['ValueError']
)
def crash_midway(ctx):
    # 1. Modify Scalar
    ctx.domain_ctx.count = 100
    # 2. Modify List
    ctx.domain_ctx.items.append(100)
    # 3. Crash
    raise ValueError("Boom!")

# --- Tests ---
class TestDeltaMechanics(unittest.TestCase):
    def setUp(self):
        self.sys = MockSystem(MockGlobal(), MockDomain())
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_inc", simple_increment)
        self.engine.register_process("p_list", list_append)
        self.engine.register_process("p_crash", crash_midway)

    def test_scalar_commit(self):
        print("\n[Delta] Testing Scalar Commit...")
        self.engine.run_process("p_inc")
        self.assertEqual(self.sys.domain_ctx.count, 1)
        print("   -> Scalar updated correctly.")

    def test_list_commit(self):
        print("\n[Delta] Testing List Commit...")
        self.engine.run_process("p_list")
        self.assertEqual(self.sys.domain_ctx.items, [99])
        print("   -> List updated correctly.")

    def test_rollback_on_crash(self):
        print("\n[Delta] Testing Rollback on Crash...")
        
        # Initial State
        self.sys.domain_ctx.count = 0
        self.sys.domain_ctx.items = [1, 2]
        
        try:
            self.engine.run_process("p_crash")
        except ValueError:
            pass # Expected crash
            
        # Verify Rollback
        print(f"   State after crash: count={self.sys.domain_ctx.count}, items={self.sys.domain_ctx.items}")
        
        # Check Scalar Rollback
        self.assertEqual(self.sys.domain_ctx.count, 0, "Scalar should be rolled back to 0")
        
        # Check List Rollback
        self.assertEqual(self.sys.domain_ctx.items, [1, 2], "List should be rolled back to [1, 2]")
        
        print("   -> Rollback successful.")

if __name__ == "__main__":
    unittest.main()
