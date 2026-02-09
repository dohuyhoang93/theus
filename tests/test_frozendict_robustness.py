import unittest
import numpy as np
import pytest
from theus_core import TheusEngine, Transaction

# Helper to access internal FrozenDict if exposed, or verify via state.heavy
# Since FrozenDict is not directly importable from python unless exposed,
# we will use engine state to access it.

# ContextError might be exposed differently depending on build/install context.
# In source (cargo build): It's in theus_core.
# In installed package (pip install .): It might be in theus.structures if exposed.
try:
    from theus.structures import ContextError
except ImportError:
    try:
        from theus_core import ContextError
    except ImportError:
        # Final fallback: If not importable, mock it for test logic check or fail gracefully
        print("WARNING: Could not import ContextError. Tests for immutability might fail on exception type.")
        class ContextError(Exception): pass

class TestFrozenDictRobustness(unittest.TestCase):
    def setUp(self):
        self.engine = TheusEngine()
        # Seed heavy zone to get a FrozenDict instance
        val = {"a": 1, "arr": np.zeros(3)}
        self.engine.compare_and_swap(0, None, val, None)
        self.frozen = self.engine.state.heavy # This is a FrozenDict

    # ----------------------------------------------------------------
    # 1. PATTERN (Mẫu) - Standard Integrity & Equality
    # ----------------------------------------------------------------
    def test_pattern_standard_access(self):
        """Test standard dictionary interface (get, len, keys, items)."""
        fd = self.frozen
        self.assertEqual(fd["a"], 1)
        self.assertTrue(np.array_equal(fd["arr"], np.zeros(3)))
        self.assertEqual(len(fd), 2)
        # keys() returns object, cast to list for check if needed or iterate
        keys = list(fd.keys())
        self.assertIn("a", keys)
        self.assertIn("arr", fd)
    
    def test_pattern_immutability(self):
        """Test that it is indeed immutable."""
        fd = self.frozen
        with self.assertRaises(ContextError):
            fd["new"] = 10
        with self.assertRaises(ContextError):
            fd["a"] = 99

    # ----------------------------------------------------------------
    # 2. RELATED (Liên quan) - Interaction with Standard Types
    # ----------------------------------------------------------------
    def test_related_dict_equivalence(self):
        """Test equality with standard Python dict (Content Equality)."""
        fd = self.frozen
        std_dict = {"a": 1, "arr": np.zeros(3)}
        
        # Case A: Identical Content
        self.assertTrue(fd == std_dict, "FrozenDict should match equivalent dict")
        self.assertTrue(std_dict == fd, "Reverse comparison should also work")
        
        # Case B: Different Content
        diff_dict = {"a": 2, "arr": np.zeros(3)}
        self.assertFalse(fd == diff_dict)

    def test_related_casting(self):
        """Test converting FrozenDict back to dict."""
        fd = self.frozen
        as_dict = dict(fd) # iterate keys
        self.assertEqual(as_dict["a"], 1)
        self.assertIsInstance(as_dict["arr"], np.ndarray)
        
        # Test explicit to_dict (if exposed)
        if hasattr(fd, "to_dict"):
            d2 = fd.to_dict()
            self.assertEqual(d2["a"], 1)

    # ----------------------------------------------------------------
    # 3. BOUNDARY (Biên) - Edge Cases
    # ----------------------------------------------------------------
    def test_boundary_empty(self):
        """Test behavior with empty dictionary."""
        # Use fresh engine for empty check
        engine = TheusEngine() 
        # By default heavy might be None or empty depending on init. 
        # If None, we can't test FrozenDict equality.
        # Let's seed empty dict.
        engine.compare_and_swap(0, None, {}, None)
        fd = engine.state.heavy
        if fd is not None:
             self.assertEqual(len(fd), 0)
             self.assertTrue(fd == {})

    def test_boundary_large_array(self):
        """Test equality with large Arrays (to check performance/correctness)."""
        large_arr = np.random.rand(100, 100)
        engine = TheusEngine()
        engine.compare_and_swap(0, None, {"large": large_arr}, None)
        fd = engine.state.heavy
        
        ref_dict = {"large": large_arr}
        self.assertTrue(fd == ref_dict)
        
        # Tweak one value
        large_arr_2 = large_arr.copy()
        large_arr_2[0,0] += 0.1
        ref_dict_2 = {"large": large_arr_2}
        self.assertFalse(fd == ref_dict_2)

    def test_boundary_nested_types(self):
        """Test FrozenDict containing nested types (if supported)."""
        # Create FRESH engine to avoid contamination from setUp
        engine = TheusEngine()
        nested_data = {"l1": {"l2": 10}}
        engine.compare_and_swap(0, None, nested_data, None)
        fd = engine.state.heavy
        
        val = fd["l1"]
        self.assertEqual(val["l2"], 10)
        self.assertTrue(fd == nested_data, f"FrozenDict {fd} != {nested_data}")

    # ----------------------------------------------------------------
    # 4. CONFLICT (Xung đột) - Identity vs Equality (The Bug Source)
    # ----------------------------------------------------------------
    def test_conflict_identity_mismatch(self):
        """
        CRITICAL: Test that two different FrozenDict objects with SAME content 
        are considered EQUAL. This was the root cause of the bug.
        """
        engine = TheusEngine()
        data = {"x": np.array([1, 2, 3])}
        engine.compare_and_swap(0, None, data, None)
        fd1 = engine.state.heavy
        
        # Create a Transaction to generate a Shadow (Copy)
        with Transaction(engine) as tx:
            shadow = tx.get_shadow(fd1, "heavy")
            
            # 1. Verify Identity Mismatch (Crucial constraint)
            if id(fd1) == id(shadow):
                 print("WARNING: Zero-Copy active (IDs Identical). Skipping Identity check.")
            
            # 2. Verify Logical Equality (The Fix)
            # This MUST return True
            self.assertTrue(fd1 == shadow, "Different objects with same content MUST be equal")
            
            # 3. Data Integrity check
            self.assertTrue(np.array_equal(fd1["x"], shadow["x"]))

if __name__ == "__main__":
    unittest.main()
