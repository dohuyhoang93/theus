
import pytest
import tempfile
import numpy as np
import shutil
import theus
from theus import TheusEngine, BaseSystemContext, BaseDomainContext
from dataclasses import dataclass, field
from typing import Dict, Any

# --- Setup Context ---
@dataclass
class NumPyDomain(BaseDomainContext):
    arrays: Dict[str, Any] = field(default_factory=dict)
    mixed: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NumPyContext(BaseSystemContext):
    domain: NumPyDomain = field(default_factory=NumPyDomain)


class TestNumPyEquality:
    """
    Validates that Theus Core handles NumPy array equality checks correctly
    during 'infer_shadow_deltas' without raising 'ValueError: The truth value of an array is ambiguous'.
    """

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.ctx = NumPyContext(
            domain=NumPyDomain(
                arrays={
                    "simple": np.array([1, 2, 3]),
                    "matrix": np.zeros((10, 10))
                },
                mixed={}
            ),
            global_ctx=theus.BaseGlobalContext()
        )
        self.engine = TheusEngine(self.ctx)

    def teardown_method(self):
        shutil.rmtree(self.tmp)

    def test_numpy_shadow_mutation(self):
        """
        Scenario: Mutate NumPy array in-place via Proxy.
        Expectation: infer_shadow_deltas detects change using (a==b).all() logic
        instead of native comparison (which crashes).
        """
        print("\n[Test] Mutating NumPy Array via Proxy...")
        
        with self.engine.transaction() as tx:
            # 1. Access array (Creates Shadow)
            arr = self.ctx.domain.arrays["simple"]
            
            # 2. Mutate in-plce
            arr[0] = 99
            
            # 3. Commit triggers infer_shadow_deltas
            # Theus Core must compare Shadow([99, 2, 3]) vs Original([1, 2, 3])
            # This triggers numpy equality check.
        
        # Verify Persistence
        result = self.engine.state.data["domain"]["arrays"]["simple"]
        assert result[0] == 99, "Mutation was not committed!"
        print(" -> Success: Array mutated and committed without crash.")

    def test_numpy_no_change(self):
        """
        Scenario: Access but do not mutate.
        Expectation: Equality check returns True (all elements equal). No delta log.
        """
        print("\n[Test] Accessing NumPy Array without mutation...")
        
        with self.engine.transaction() as tx:
            arr = self.ctx.domain.arrays["matrix"]
            # Just read it
            _ = arr[0, 0]
            
        # Verify no crash
        print(" -> Success: No crash on equality check for identical arrays.")

    def test_numpy_replacement(self):
        """
        Scenario: Replace array with new array.
        Expectation: This is standard assignment, handled by set_item, not infer.
        But let's verify consistent handling.
        """
        new_arr = np.array([10, 20])
        
        with self.engine.transaction() as tx:
            self.ctx.domain.arrays["simple"] = new_arr
            
        res = self.engine.state.data["domain"]["arrays"]["simple"]
        assert np.array_equal(res, new_arr)

