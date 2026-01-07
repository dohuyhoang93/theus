import unittest
from dataclasses import dataclass, field
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext, ContractViolationError

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class DeepConfig:
    val: int = 10

@dataclass
class MockDomain(BaseDomainContext):
    # domain.config.val
    config: DeepConfig = field(default_factory=DeepConfig)

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

@process(
    inputs=['domain_ctx.config.val'],
    outputs=[]
)
def read_deep(ctx):
    # To read val, we must access ctx.domain_ctx.config first
    # This is "domain.config"
    # It is NOT in inputs. 
    # Current Guard checks if "domain.config" is in inputs OR if parent ("domain") is in inputs.
    # Neither is true. inputs has "domain.config.val".
    val = ctx.domain_ctx.config.val
    return val

class TestTraversal(unittest.TestCase):
    def setUp(self):
        self.sys = MockSystem(MockGlobal(), MockDomain())
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_deep", read_deep)

    def test_deep_access(self):
        print("\n[Audit] Testing Deep Path Traversal...")
        
        try:
            val = self.engine.run_process("p_deep")
            print(f"   Success! Value: {val}")
        except ContractViolationError as e:
            print(f"   Caught Expected Error: {e}")
            self.fail("Traversal Mocked! Guard prevented accessing intermediate path 'domain_ctx.config' despite leaf being allowed.")

if __name__ == "__main__":
    unittest.main()
