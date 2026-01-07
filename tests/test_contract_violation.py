import sys
import os
import unittest
import torch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataclasses import dataclass
from typing import Any, List, Dict
from theus.context import BaseGlobalContext, BaseDomainContext, BaseSystemContext as SystemContext
from theus import TheusEngine, process
from theus.contracts import ContractViolationError

@dataclass
class GlobalContext(BaseGlobalContext):
    initial_needs: List[float] = None
    initial_emotions: List[float] = None
    total_episodes: int = 0
    max_steps: int = 0
    seed: int = 0
    switch_locations: Dict = None
    initial_exploration_rate: float = 1.0

@dataclass
class DomainContext(BaseDomainContext):
    N_vector: Any = None
    E_vector: Any = None
    believed_switch_states: Dict = None
    q_table: Dict = None
    short_term_memory: List = None
    long_term_memory: Dict = None
    base_exploration_rate: float = 0.0
    current_exploration_rate: float = 0.0
    selected_action: Any = None
    last_reward: Any = None
    current_observation: Any = None

class TestContractEnforcement(unittest.TestCase):
    def setUp(self):
        # Setup Dummy Context
        global_ctx = GlobalContext(
            initial_needs=[0.5], initial_emotions=[0.0], total_episodes=1, max_steps=10, seed=42
        )
        domain_ctx = DomainContext(
            N_vector=torch.tensor([0.5]), E_vector=torch.tensor([0.0]),
            believed_switch_states={}, q_table={}, short_term_memory=[], long_term_memory={}
        )
        self.sys_ctx = SystemContext(global_ctx=global_ctx, domain_ctx=domain_ctx)
        self.engine = TheusEngine(self.sys_ctx)

    def test_illegal_write_violation(self):
        """Test catching a write to an undeclared output."""
        
        # Define a process that writes to 'domain_ctx.td_error' but does NOT declare it
        @process(inputs=[], outputs=['domain_ctx.current_step']) # Missing 'domain_ctx.td_error'
        def bad_writer(ctx):
            ctx.domain_ctx.current_step = 1 # OK
            ctx.domain_ctx.td_error = 0.5   # VIOLATION!
            
        self.engine.register_process("bad_writer", bad_writer)
        
        print("\n[Test] Illegal Write Violation...")
        # Rust Engine raises PermissionError, which is acceptable form of Contract Enforcement
        with self.assertRaises((ContractViolationError, PermissionError)) as cm:
            self.engine.run_process("bad_writer")
        
        print(f"   -> Caught Expected Error: {cm.exception}")
        # Message might differ
        self.assertTrue("Illegal Write" in str(cm.exception) or "Violation" in str(cm.exception))

    def test_undeclared_error_violation(self):
        """Test catching an undeclared exception."""
        
        @process(inputs=[], outputs=[], errors=['ValueError']) # Declares ValueError
        def bad_error(ctx):
            raise TypeError("I am a TypeError") # VIOLATION (Not in errors list)
            
        self.engine.register_process("bad_error", bad_error)
        
        print("\n[Test] Undeclared Error Violation...")
        with self.assertRaises(ContractViolationError) as cm:
            self.engine.run_process("bad_error")
            
        print(f"   -> Caught Expected Error: {cm.exception}")
        self.assertIn("Undeclared Error Violation", str(cm.exception))
        self.assertIn("TypeError", str(cm.exception))

    def test_valid_execution(self):
        """Test that valid contracts pass."""
        
        @process(inputs=[], outputs=['domain_ctx.current_step'])
        def good_process(ctx):
            ctx.domain_ctx.current_step = 99
            
        self.engine.register_process("good_process", good_process)
        
        self.engine.run_process("good_process")
        self.assertEqual(self.sys_ctx.domain_ctx.current_step, 99)
        print("\n[Test] Valid Execution -> OK")

if __name__ == "__main__":
    unittest.main()
