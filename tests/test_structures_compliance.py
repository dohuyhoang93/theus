
import sys
import os
import unittest

# Ensure we import the INSTALLED package which has the Rust Extension
# Remove local path insertion if it conflicts, but we need to find tests.
# Actually, we rely on 'theus' being installed.
# We remove the sys.path hack to test the installed wheel.

from theus.structures import TrackedDict, TrackedList
from theus_core import Transaction

class TestTrackedStructures(unittest.TestCase):
    def setUp(self):
        self.tx = Transaction() # Real Rust Transaction
        
    def test_dict_compliance(self):
        shadow = {"a": 1, "b": 2} 
        d = TrackedDict(shadow, self.tx, "root")
        
        # Test pop
        val = d.pop("a")
        self.assertEqual(val, 1)
        self.assertNotIn("a", d)
        
        # Check logs. Rust Transaction stores DeltaEntry objects.
        # last_entry = self.tx.delta_log[-1]
        # entry.op should be "POP"
        last_entry = self.tx.delta_log[-1]
        self.assertEqual(last_entry.op, "POP")
        
        # Test setdefault (new key)
        val = d.setdefault("c", 3)
        self.assertEqual(val, 3)
        self.assertEqual(d["c"], 3)
        self.assertEqual(self.tx.delta_log[-1].op, "SET")

        # Test popitem
        k, v = d.popitem()
        self.assertEqual(k, "c") 
        self.assertEqual(self.tx.delta_log[-1].op, "POPITEM")
        
        # Test update
        d.update({"x": 10})
        self.assertEqual(d["x"], 10)
        # Update iterates and Sets
        self.assertEqual(self.tx.delta_log[-1].op, "SET")
        
        # Test clear
        d.clear()
        self.assertEqual(len(d), 0)
        self.assertEqual(self.tx.delta_log[-1].op, "CLEAR")

    def test_list_compliance(self):
        shadow = [3, 1, 2]
        l = TrackedList(shadow, self.tx, "root")
        
        # Test sort
        l.sort()
        self.assertEqual(list(l), [1, 2, 3])
        self.assertEqual(self.tx.delta_log[-1].op, "SORT")
        
        # Test reverse
        l.reverse()
        self.assertEqual(list(l), [3, 2, 1])
        self.assertEqual(self.tx.delta_log[-1].op, "REVERSE")
        
        # Test clear
        l.clear()
        self.assertEqual(len(l), 0)
        self.assertEqual(self.tx.delta_log[-1].op, "CLEAR")

if __name__ == '__main__':
    unittest.main()
