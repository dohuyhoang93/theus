
import time
import numpy as np
import unittest
import theus_core

class TestZeroCopyProof(unittest.TestCase):
    def setUp(self):
        self.engine = theus_core.TheusEngine()
        # 500MB of data
        self.large_data = np.random.rand(62_500_000) # 62.5M floats * 8 = 500MB
        
        # Hydrate
        self.engine.compare_and_swap(0, {"payload": self.large_data}, {"payload": self.large_data}, None)

    def test_proof(self):
        print("\n--- [PROOF 1] PERFORMANCE: O(1) vs O(N) ---")
        st = self.engine.state
        
        with theus_core.Transaction(self.engine) as tx:
            # 1. Measure Data Zone (Strict Deepcopy)
            start = time.perf_counter()
            d_shadow = tx.get_shadow(st.data, "domain")
            data_time = (time.perf_counter() - start) * 1000
            print(f"Data Zone Shadow (Deepcopy 500MB):  {data_time:7.2f} ms")
            
            # 2. Measure Heavy Zone (Zero-Copy)
            start = time.perf_counter()
            h_shadow = tx.get_shadow(st.heavy, "heavy")
            heavy_time = (time.perf_counter() - start) * 1000
            print(f"Heavy Zone Shadow (Zero-Copy):       {heavy_time:7.2f} ms")
            
            print(f"Speedup Ratio: {data_time / (heavy_time if heavy_time > 0 else 0.001):.1f}x")
            
            # Verification
            self.assertLess(heavy_time, 2.0, "Heavy zone MUST be O(1) [near-instant].")
            self.assertLess(heavy_time, data_time / 10, "Heavy zone MUST be significantly faster for large data.")

        print("\n--- [PROOF 2] MEMORY: RAW DATA POINTERS ---")
        original_ptr = self.large_data.__array_interface__['data'][0]
        
        with theus_core.Transaction(self.engine) as tx:
            d_shadow = tx.get_shadow(st.data, "domain")
            h_shadow = tx.get_shadow(st.heavy, "heavy")
            
            d_ptr = d_shadow['payload'].__array_interface__['data'][0]
            h_ptr = h_shadow['payload'].__array_interface__['data'][0]
            
            print(f"Original Buffer Pointer: {original_ptr}")
            print(f"Data Zone Shadow Pointer: {d_ptr}")
            print(f"Heavy Zone Shadow Pointer: {h_ptr}")
            
            # PROOF:
            # Data Zone MUST have a DIFFERENT pointer (it was copied)
            # Heavy Zone MUST have the SAME pointer (Zero-Copy)
            self.assertNotEqual(original_ptr, d_ptr, "Data Zone failed to isolate! Pointer was shared.")
            self.assertEqual(original_ptr, h_ptr, "Heavy Zone failed Zero-Copy! Pointer was NOT shared.")
            print("✅ [POINTER PROOF SUCCESS]: Heavy Zone points to the SAME physical RAM.")

        print("\n--- [PROOF 3] THE IMPOSTER PROTECTION ---")
        fd = self.engine.state.heavy
        print(f"Type: {type(fd)}")
        self.assertIn("FrozenDict", str(type(fd)))
        
        # Verify read works
        self.assertEqual(fd['payload'].shape, (62_500_000,))
        
        # Verify write fails in Rust
        try:
            fd["immutable_test"] = 1
            self.fail("Should have raised ContextError")
        except theus_core.ContextError as e:
            print(f"Protection Verified: {e}")
        except Exception as e:
             self.fail(f"Unexpected exception: {type(e)}")

        print("✅ [PROTECTION PROOF SUCCESS]: FrozenDict shell blocks direct writes.")

if __name__ == "__main__":
    unittest.main()
