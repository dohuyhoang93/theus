
import unittest
import pickle
import numpy as np
from multiprocessing import shared_memory
from theus.context import ShmArray, rebuild_shm_array

class TestShmPickling(unittest.TestCase):
    def setUp(self):
        # 1. Create a Shared Memory Block (100MB)
        # 100MB / 8 bytes (float64) = 12.5M floats
        self.size_mb = 10
        self.elements = int(self.size_mb * 1024 * 1024 / 8)
        self.shm = shared_memory.SharedMemory(create=True, size=self.size_mb * 1024 * 1024)
        
        # 2. Create ShmArray
        raw_arr = np.ndarray((self.elements,), dtype=np.float64, buffer=self.shm.buf)
        raw_arr[:] = 1.23
        self.arr = ShmArray(raw_arr, shm=self.shm)

    def tearDown(self):
        try:
            self.shm.close()
            self.shm.unlink()
        except:
            pass

    def test_smart_pickling_size(self):
        """Verify that pickling ShmArray is tiny (Zero-Copy)."""
        # 1. Standard Pickle (if it were a normal array)
        # heavy_pickle = pickle.dumps(np.array(self.arr))
        # print(f"Normal Pickle Size: {len(heavy_pickle)} bytes")
        
        # 2. Smart Pickle
        smart_pickle = pickle.dumps(self.arr)
        size = len(smart_pickle)
        print(f"DEBUG: Smart Pickle Size: {size} bytes")
        
        # Should be < 1KB (it's just a function ref and string args)
        self.assertLess(size, 1024, "Pickle payload is too large! Smart Pickling failed.")
        
    def test_round_trip(self):
        """Verify we can reconstruct it."""
        serialized = pickle.dumps(self.arr)
        
        # Simulate passing to another process (rebuild)
        # Note: In same process, shm is already open, but rebuild_shm_array calls SharedMemory(name=...)
        # which opens a NEW handle. This is fine.
        reconstructed = pickle.loads(serialized)
        
        self.assertIsInstance(reconstructed, ShmArray)
        self.assertEqual(reconstructed[0], 1.23)
        self.assertEqual(reconstructed.shape, (self.elements,))
        
        # Clean up new handle
        reconstructed.shm.close()

if __name__ == "__main__":
    unittest.main()
