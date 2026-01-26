
import unittest
import numpy as np
from multiprocessing import shared_memory
from theus.context import HeavyZoneWrapper
try:
    from theus_core import shm
    BUFFER_DESCRIPTOR_AVAILABLE = True
except ImportError:
    BUFFER_DESCRIPTOR_AVAILABLE = False

class MockBufferDescriptor:
    """Mock for when Rust module isn't built yet in test env"""
    def __init__(self, name, size, shape, dtype):
        self.name = name
        self.size = size
        self.shape = shape
        self.dtype = dtype

class TestZeroCopyIntegration(unittest.TestCase):
    def setUp(self):
        # 1. Create a Shared Memory Block (Producer Simulation)
        self.shm = shared_memory.SharedMemory(create=True, size=1024)
        self.arr = np.ndarray((10,), dtype=np.float64, buffer=self.shm.buf)
        self.arr[:] = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8, 9.9, 10.0]
        
        # 2. Create Descriptor
        if BUFFER_DESCRIPTOR_AVAILABLE:
            self.desc = shm.BufferDescriptor(
                name=self.shm.name,
                size=1024,
                shape=[10],
                dtype='float64'
            )
        else:
            self.desc = MockBufferDescriptor(
                name=self.shm.name,
                size=1024,
                shape=[10],
                dtype='float64'
            )

    def tearDown(self):
        try:
            self.shm.close()
            self.shm.unlink()
        except:
            pass

    def test_heavy_zone_wrapper_read(self):
        """Test that HeavyZoneWrapper effectively provides Zero-Copy Read View."""
        # Setup Fake State Dict
        fake_heavy_dict = {
            "model_weights": self.desc,
            "simple_config": 42
        }
        
        # Initialize Wrapper
        heavy = HeavyZoneWrapper(fake_heavy_dict)
        
        # 1. Access Normal Item
        self.assertEqual(heavy['simple_config'], 42)
        
        # 2. Access Heavy Item (Should be Auto-Converted to Numpy)
        try:
            view = heavy['model_weights']
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to access heavy item: {e}")
            raise e
        
        print(f"DEBUG: view type: {type(view)}")
        self.assertIsInstance(view, np.ndarray, "Should be converted to numpy array")
        print(f"DEBUG: view[0] value: {view[0]}")
        
        try:
            np.testing.assert_allclose(view[0], 1.1, err_msg="Data verification failed")
            # self.assertEqual(view[0], 1.1, "Data verification failed")
        except AssertionError as e:
            print(f"ASSERTION FAILED: {e}")
            raise e
            
        # 3. Verify Zero-Copy (Address Check)
        view[0] = 99.9
        print(f"DEBUG: Modified view[0] to 99.9. Original arr[0] is now: {self.arr[0]}")
        self.assertEqual(self.arr[0], 99.9, "Write transparency check failed")
        print("✅ Zero-Copy Write Reflection Confirmed")

if __name__ == "__main__":
    unittest.main()
