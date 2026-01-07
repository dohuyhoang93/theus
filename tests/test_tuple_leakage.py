import unittest
from dataclasses import dataclass, field
from typing import List, Tuple
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class MockDomain(BaseDomainContext):
    # A tuple containing a mutable list
    immutable_container: Tuple[List[int], ...] = field(default_factory=lambda: ([1],))

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

@process(
    inputs=['domain_ctx.immutable_container'],
    outputs=['domain_ctx.immutable_container'],
    errors=['ValueError']
)
def modify_tuple_element(ctx):
    # ctx.domain.immutable_container returns (original_list,)
    # accessing [0] returns original_list
    mutable_list = ctx.domain_ctx.immutable_container[0]
    mutable_list.append(999)
    
    raise ValueError("Crash to Rollback")

class TestTupleLeakage(unittest.TestCase):
    def setUp(self):
        self.sys = MockSystem(MockGlobal(), MockDomain())
        # Ensure it's a tuple of lists
        self.sys.domain_ctx.immutable_container = ([1],)
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_tuple", modify_tuple_element)

    def test_tuple_leak(self):
        print("\n[Audit] Testing Tuple Leakage...")
        original_inner = self.sys.domain_ctx.immutable_container[0]
        print(f"   Original Before: {original_inner}")
        
        try:
            self.engine.run_process("p_tuple")
        except ValueError:
            pass
            
        final_inner = self.sys.domain_ctx.immutable_container[0]
        print(f"   Original After:  {final_inner}")
        
        # If Leak exists, final will be [1, 999]
        self.assertEqual(final_inner, [1], "CRITICAL: Tuple element mutation leaked to original context!")
        print("   -> Isolation maintained (Safe).")

if __name__ == "__main__":
    unittest.main()
