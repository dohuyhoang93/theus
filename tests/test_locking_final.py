import unittest
import os
from unittest.mock import patch
from theus import BaseGlobalContext, BaseDomainContext, BaseSystemContext, TheusEngine, process
from dataclasses import dataclass

@dataclass
class MockGlobal(BaseGlobalContext): pass

@dataclass
class MockDomain(BaseDomainContext):
    counter: int = 0

@dataclass
class MockSystem(BaseSystemContext): pass

class TestContextLocking(unittest.TestCase):
    def test_warning_mode(self):
        glob = MockGlobal()
        dom = MockDomain()
        sys_ctx = MockSystem(global_ctx=glob, domain_ctx=dom)
        
        engine = TheusEngine(sys_ctx, strict_mode=False)
        
        # Unsafe Mutation (Warning)
        with self.assertLogs("Theus.LockManager", level="WARNING") as cm:
            dom.counter = 5
        self.assertEqual(dom.counter, 5)

    def test_strict_mode(self):
        glob = MockGlobal()
        dom = MockDomain()
        sys_ctx = MockSystem(global_ctx=glob, domain_ctx=dom)
        
        # Explicit Strict Mode
        engine = TheusEngine(sys_ctx, strict_mode=True)
        
        # Capture the EXACT class used by this engine instance
        ErrorClass = engine.lock_manager.LockViolationError
        
        with self.assertRaises(ErrorClass):
            dom.counter = 99
        self.assertEqual(dom.counter, 0)
            
    def test_env_var_strict(self):
        glob = MockGlobal()
        dom = MockDomain()
        sys_ctx = MockSystem(global_ctx=glob, domain_ctx=dom)
        
        with patch.dict(os.environ, {"POP_STRICT_MODE": "1"}):
            engine = TheusEngine(sys_ctx)
            self.assertTrue(engine.lock_manager.strict_mode)
            
            ErrorClass = engine.lock_manager.LockViolationError
            with self.assertRaises(ErrorClass):
                dom.counter = 999

if __name__ == "__main__":
    unittest.main()
