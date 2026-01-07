import unittest
from dataclasses import dataclass, field
from typing import List
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class StatefulObject:
    value: int = 0
    
    def increment(self):
        # Side-effect on self
        self.value += 1

@dataclass
class MockDomain(BaseDomainContext):
    obj: StatefulObject = field(default_factory=StatefulObject)

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

@process(
    inputs=['domain_ctx.obj'],
    outputs=['domain_ctx.obj'], # Even if declared as output, method call prevents interception?
    errors=['ValueError']
)
def unsafe_method_call(ctx):
    # ctx.domain_ctx.obj returns the Original Object (because it's not a list/dict)
    # The guard doesn't shadow custom objects, only list/dict.
    # Calling method works on Original.
    ctx.domain_ctx.obj.increment()
    
    # Crash to trigger "Rollback"
    raise ValueError("Crash!")

class TestMethodLeakage(unittest.TestCase):
    def setUp(self):
        self.sys = MockSystem(MockGlobal(), MockDomain())
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_method", unsafe_method_call)

    def test_method_leak(self):
        print("\n[Audit] Testing Method Side-Effect Leakage...")
        print(f"   Value Before: {self.sys.domain_ctx.obj.value}")
        
        try:
            self.engine.run_process("p_method")
        except ValueError:
            pass
            
        final_val = self.sys.domain_ctx.obj.value
        print(f"   Value After:  {final_val}")
        
        # If Leak exists, final_val will be 1 (Rollback failed)
        self.assertEqual(final_val, 0, "CRITICAL: Method call side-effect leaked! Rollback bypassed.")
        print("   -> Isolation maintained (Safe).")

if __name__ == "__main__":
    unittest.main()
