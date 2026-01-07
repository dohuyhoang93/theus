import unittest
from dataclasses import dataclass, field
from typing import List
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class MockDomain(BaseDomainContext):
    # List of Lists
    matrix: List[List[int]] = field(default_factory=lambda: [[1], [2], [3]])

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

@process(
    inputs=['domain_ctx.matrix'],
    outputs=['domain_ctx.matrix']
)
def modify_via_slice(ctx):
    # Slice the first 2 elements
    # s is a new TrackedList wrapping a copy of the slice [shadow1, shadow2]
    s = ctx.domain_ctx.matrix[0:2]
    
    # Modify the first element of the slice (shared ref to shadow1)
    s[0].append(999)
    
    return "Sliced"

class TestSliceMutation(unittest.TestCase):
    def setUp(self):
        self.sys = MockSystem(MockGlobal(), MockDomain())
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_slice", modify_via_slice)

    def test_slice_mutation(self):
        print("\n[Audit] Testing Slice Mutation...")
        
        self.engine.run_process("p_slice")
        
        final_val = self.sys.domain_ctx.matrix[0]
        print(f"   Value After: {final_val}")
        
        # In Python, mod via slice affects original.
        # So we expect [1, 999].
        self.assertEqual(final_val, [1, 999], "Slice mutation failed to propagate to context!")
        
        print("   -> Slice mutation preserved (Shadow shared successfully).")

if __name__ == "__main__":
    unittest.main()
