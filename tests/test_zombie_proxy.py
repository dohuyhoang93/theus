import unittest
from dataclasses import dataclass, field
from typing import List, Any
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class MockDomain(BaseDomainContext):
    data: List[int] = field(default_factory=list)
    storage: Any = None # Leaked proxy storage

@dataclass
class MockSystem(BaseSystemContext):
    global_ctx: MockGlobal
    domain_ctx: MockDomain

# Process 1: Leaks the Proxy
@process(
    inputs=['domain_ctx.data', 'domain_ctx.storage'],
    outputs=['domain_ctx.storage']
)
def leak_proxy(ctx):
    tracked_list = ctx.domain_ctx.data
    ctx.domain_ctx.storage = tracked_list
    return "Leaked"

# Process 2: Accesses the Zombie
@process(
    inputs=['domain_ctx.storage'],
    outputs=['domain_ctx.storage']
)
def touch_zombie(ctx):
    ctx.domain_ctx.storage.append(999)
    return "Touched"

class TestZombieProxy(unittest.TestCase):
    def setUp(self):
        self.sys = MockSystem(MockGlobal(), MockDomain())
        self.sys.domain_ctx.data = [1, 2, 3]
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("p_leak", leak_proxy)
        self.engine.register_process("p_touch", touch_zombie)

    def test_zombie_proxy(self):
        print("\n[Audit] Testing Zombie Proxy Leakage...")
        
        # 1. Run Leak Process
        self.engine.run_process("p_leak")
        print(f"   Storage Type After Leak: {type(self.sys.domain_ctx.storage)}")
        
        # Check if it is indeed a TrackedList
        from theus.structures import TrackedList
        self.assertTrue(isinstance(self.sys.domain_ctx.storage, list), 
                        "Expected storage to hold unwrapped List (Zombie Fix working).")
        
        # 2. Run Touch Process
        print("   Running Touch Process (should fail or behave weirdly)...")
        try:
            self.engine.run_process("p_touch")
        except Exception as e:
            print(f"   Caught Expected Error: {e}")
            return # Test passed if it fails comfortably
            
        # If it didn't crash, let's see what happened
        print(f"   Storage Content: {self.sys.domain_ctx.storage}")
        
        real_storage = self.sys.domain_ctx.storage
        if 999 not in real_storage:
             print("   CRITICAL: Mutation LOST! The system silently ignored the update.")
             self.fail("Mutation was silent lost due to Zombie Proxy.")
        else:
             print("   Success! Storage updated (Mutation Preserved).")
             print("   Note: Aliasing is lost (storage != data) due to Shadow Copy strategy, which is expected.")

if __name__ == "__main__":
    unittest.main()
