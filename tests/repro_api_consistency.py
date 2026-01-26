
import sys
import unittest
from dataclasses import dataclass
from theus.context import LockedContextMixin
from theus.locks import LockManager

class MockLockManager(LockManager):
    def validate_write(self, name, obj):
        if name == "forbidden":
            raise PermissionError(f"Cannot write to {name}")

@dataclass
class TestContext(LockedContextMixin):
    allowed: int = 0
    forbidden: int = 0

class TestAPIConsistency(unittest.TestCase):
    def test_direct_assignment(self):
        ctx = TestContext()
        lock_mgr = MockLockManager()
        ctx.set_lock_manager(lock_mgr)
        
        # Should succeed
        ctx.allowed = 10
        self.assertEqual(ctx.allowed, 10)
        
        # Should fail
        with self.assertRaises(PermissionError):
            ctx.forbidden = 20

    def test_dict_access_simulation(self):
        # Simulation of "ctx.data['key'] = val" pattern
        # This depends on how ctx.data is implemented. 
        # If ctx.data is a dict, assignment works unless it's a FrozenDict.
        
        data = {"key": "value"}
        # If it's a standard dict, this works:
        data['key'] = "new_value"
        
        # Implementing a mock FrozenDict
        class FrozenDict(dict):
            def __setitem__(self, key, value):
                raise TypeError("FrozenDict is immutable")
                
        frozen_data = FrozenDict({"key": "value"})
        
        with self.assertRaises(TypeError):
            frozen_data['key'] = "should fail"

if __name__ == '__main__':
    unittest.main()
