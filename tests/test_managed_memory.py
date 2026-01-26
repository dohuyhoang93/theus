
import unittest
import numpy as np
import time
import os
import sys
from multiprocessing import shared_memory
from theus.context import HeavyZoneAllocator, ShmArray

class TestManagedMemory(unittest.TestCase):
    def setUp(self):
        self.allocator = HeavyZoneAllocator()
        self.created_names = []

    def tearDown(self):
        self.allocator.cleanup()
        # Double check cleanup
        for name in self.created_names:
            try:
                shm = shared_memory.SharedMemory(name=name)
                shm.close()
                shm.unlink()
            except FileNotFoundError:
                pass

    def test_alloc_lifecycle(self):
        """Verify allocation creates accessible SHM and cleanup removes it."""
        shape = (100,)
        arr = self.allocator.alloc("test_lifecycle", shape, np.int32)
        
        self.assertIsInstance(arr, ShmArray)
        self.assertIsNotNone(arr.shm)
        name = arr.shm.name
        self.created_names.append(name)
        
        # Verify name structure
        # theus:{session}:{pid}:{key}
        parts = name.split(':')
        self.assertEqual(parts[0], "theus")
        self.assertEqual(parts[3], "test_lifecycle")
        
        # Write data
        arr[:] = 99
        
        # Access from "another process" (simulated via new generic SharedMemory)
        shm2 = shared_memory.SharedMemory(name=name)
        arr2 = np.ndarray(shape, dtype=np.int32, buffer=shm2.buf)
        self.assertEqual(arr2[0], 99)
        shm2.close()
        
        # Cleanup
        self.allocator.cleanup()
        
        # Verify Gone
        with self.assertRaises(FileNotFoundError):
             shared_memory.SharedMemory(name=name)

    def test_namespace_audit(self):
        """Verify different keys generate different segments."""
        arr1 = self.allocator.alloc("key1", (10,), np.float32)
        arr2 = self.allocator.alloc("key2", (10,), np.float32)
        
        self.assertNotEqual(arr1.shm.name, arr2.shm.name)
        self.created_names.append(arr1.shm.name)
        self.created_names.append(arr2.shm.name)

    def test_zombie_recovery(self):
        """Verify Allocator cleans up zombies from registry on startup."""
        import json
        
        # 1. Simulate a Zombie Record
        fake_pid = 99999999 # Impossible PID
        fake_session = "zombie_sess"
        zombie_name = f"theus:{fake_session}:{fake_pid}:zombie_data"
        registry_file = ".theus_memory_registry.jsonl"
        
        # Create actual SHM for the zombie
        shm = shared_memory.SharedMemory(create=True, size=1024, name=zombie_name)
        # We manually close it here so we don't hold handle, but file remains valid
        shm.close()
        
        try:
            # Inject into Registry
            with open(registry_file, "a") as f:
                rec = {
                    "name": zombie_name,
                    "pid": fake_pid, 
                    "session": fake_session,
                    "size": 1024,
                    "ts": time.time()
                }
                f.write(json.dumps(rec) + "\n")
            
            # 2. TRIGGER SCAN (Re-init Allocator)
            # The act of creating a NEW allocator should trigger scan_zombies
            new_allocator = HeavyZoneAllocator()
            new_allocator.cleanup() # clean its own stuff
            
            # 3. Verify Zombie is Dead
            with self.assertRaises(FileNotFoundError):
                 shared_memory.SharedMemory(name=zombie_name)
                 
        finally:
            # Cleanup if test failed
            try:
                s = shared_memory.SharedMemory(name=zombie_name)
                s.close()
                s.unlink()
            except:
                pass

    def test_strict_ownership(self):
        """Verify Borrowers (rebuilt ShmArray) cannot unlink."""
        # 1. Alloc by Owner
        arr = self.allocator.alloc("my_secret", (10,), np.int32)
        
        # 2. Simulate Serialization (Pickle) -> Deserialization (Unpickle) in Worker
        import pickle
        dumped = pickle.dumps(arr)
        
        # 3. Simulate Borrower
        borrowed_arr = pickle.loads(dumped)
        
        # Verify it looks like original
        self.assertEqual(borrowed_arr.shape, (10,))
        self.assertIsNotNone(borrowed_arr.shm)
        
        # 4. Attempt Illegal Unlink
        with self.assertRaises(PermissionError):
            borrowed_arr.shm.unlink()
            
        # 5. Verify data is still there (Owner wasn't affected)
        # If unlink succeeded (fail), this would crash or be gone
        try:
             s = shared_memory.SharedMemory(name=arr.shm.name)
             s.close()
        except FileNotFoundError:
             self.fail("Memory was unlinked despite Protection!")
             
if __name__ == "__main__":
    unittest.main()
