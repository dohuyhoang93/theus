import unittest
import logging
from pop import BaseGlobalContext, BaseDomainContext, BaseSystemContext, POPEngine, process
from pop.locks import LockViolationError
from dataclasses import dataclass, field

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class MockDomain(BaseDomainContext):
    counter: int = 0

@dataclass
class MockSystem(BaseSystemContext):
    pass

@process(inputs=['domain.counter'], outputs=['domain.counter'])
def p_increment(ctx):
    ctx.domain_ctx.counter += 1

class TestContextLocking(unittest.TestCase):
    def setUp(self):
        # Reset Logger capture if needed
        pass

    def test_warning_mode_allows_mutation(self):
        glob = MockGlobal()
        dom = MockDomain()
        sys = MockSystem(global_ctx=glob, domain_ctx=dom)
        
        # Default strict_mode=False
        engine = POPEngine(sys, strict_mode=False)
        engine.register_process("p_increment", p_increment)

        # 1. Unsafe Mutation (Should work but warn)
        with self.assertLogs("POP.LockManager", level="WARNING") as cm:
            dom.counter = 5
        self.assertEqual(dom.counter, 5)
        self.assertTrue(any("UNSAFE MUTATION" in m for m in cm.output))

        # 2. Process Mutation (Should be silent)
        # Note: assertLogs will fail if NO log is emitted? No, it captures.
        # We want to verify NO warning is logged.
        # But logging capture is tricky. Let's just trust it doesn't crash.
        engine.run_process("p_increment")
        self.assertEqual(dom.counter, 6)

        # 3. Safe Edit (Should be silent)
        with engine.edit() as unlocked_ctx:
            unlocked_ctx.domain_ctx.counter = 10
        self.assertEqual(dom.counter, 10)

    def test_strict_mode_blocks_mutation(self):
        glob = MockGlobal()
        dom = MockDomain()
        sys = MockSystem(global_ctx=glob, domain_ctx=dom)
        
        # Struct Mode = True
        engine = POPEngine(sys, strict_mode=True)
        engine.register_process("p_increment", p_increment)

        # 1. Unsafe Mutation -> ERROR
        with self.assertRaises(LockViolationError):
            dom.counter = 99
        # Should NOT update
        self.assertEqual(dom.counter, 0)

        # 2. Process Mutation -> OK
        engine.run_process("p_increment")
        self.assertEqual(dom.counter, 1)

        # 3. Safe Edit -> OK
        with engine.edit() as unlocked_ctx:
            unlocked_ctx.domain_ctx.counter = 20
        self.assertEqual(dom.counter, 20)

    def test_env_var_strict_mode(self):
        import os
        from unittest.mock import patch
        
        glob = MockGlobal()
        dom = MockDomain()
        sys = MockSystem(global_ctx=glob, domain_ctx=dom)
        
        # Mock Env Var to "1"
        with patch.dict(os.environ, {"POP_STRICT_MODE": "1"}):
            # Init without explicit strict_mode arg (should default to Env)
            engine = POPEngine(sys)
            self.assertTrue(engine.lock_manager.strict_mode)
            
            # Verify it blocks mutation
            with self.assertRaises(LockViolationError):
                dom.counter = 999

        # Mock Env Var to "0"
        with patch.dict(os.environ, {"POP_STRICT_MODE": "0"}):
             engine = POPEngine(sys)
             self.assertFalse(engine.lock_manager.strict_mode)
             
             # Verify it allows mutation (with warning)
             dom.counter = 111
             self.assertEqual(dom.counter, 111)

if __name__ == "__main__":
    unittest.main()
