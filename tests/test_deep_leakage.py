import unittest
from dataclasses import dataclass, field
from typing import List
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class MockDomain(BaseDomainContext):
    matrix: List[List[int]] = field(default_factory=list)

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

@process(
    inputs=['domain_ctx.matrix'],
    outputs=['domain_ctx.matrix'],
    errors=['ValueError']  # For crash test
)
def nested_append(ctx):
    # This should modify the SHADOW, not the original yet.
    # ctx.domain_ctx.matrix is a TrackedList(shadow_matrix)
    # ctx.domain_ctx.matrix[0] is the inner list.
    # If Shallow Copy was used, matrix[0] IS the original inner list.
    ctx.domain_ctx.matrix[0].append(999)
    # Then we crash to trigger rollback
    raise ValueError("Crash to trigger rollback")

class TestDeepLeakage(unittest.TestCase):
    def setUp(self):
        # Setup: [[1]]
        self.sys = MockSystem(MockGlobal(), MockDomain())
        self.sys.domain_ctx.matrix = [[1]]
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_nested", nested_append)

    def test_nested_leak(self):
        print("\n[Audit] Testing Nested Mutation Leakage...")
        original_inner = self.sys.domain_ctx.matrix[0]
        print(f"   Original Before: {original_inner}")
        
        try:
            self.engine.run_process("p_nested")
        except ValueError:
            pass
            
        final_inner = self.sys.domain_ctx.matrix[0]
        print(f"   Original After:  {final_inner}")
        
        # If Rollback works perfectly, final should be [1].
        # If Leak exists, final will be [1, 999].
        self.assertEqual(final_inner, [1], "CRITICAL: Nested mutation leaked to original context despite Rollback!")
        print("   -> Isolation maintained (Safe).")

if __name__ == "__main__":
    unittest.main()
