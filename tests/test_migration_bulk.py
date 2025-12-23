import sys
import os
import torch
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataclasses import dataclass
from typing import Any, List, Dict
from theus.context import BaseGlobalContext, BaseDomainContext, BaseSystemContext as SystemContext
from theus import TheusEngine
from src.adapters.environment_adapter import EnvironmentAdapter

@dataclass
class GlobalContext(BaseGlobalContext):
    initial_needs: List[float] = None
    initial_emotions: List[float] = None
    total_episodes: int = 0
    max_steps: int = 0
    seed: int = 0
    switch_locations: Dict = None
    initial_exploration_rate: float = 1.0
    exploration_decay: float = 0.99
    emotional_boost_factor: float = 0.0
    min_exploration: float = 0.1
    learning_rate: float = 0.1
    discount_factor: float = 0.95
    use_dynamic_curiosity: bool = False
    use_adaptive_fatigue: bool = False
    fatigue_growth_rate: float = 0.0
    short_term_memory_limit: int = 100
    intrinsic_reward_weight: float = 0.1 # Added for p8 compatibility

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
    previous_observation: Any = None # Added for p7 compatibility
    emotion_model: Any = None # Added for p3 compatibility
    td_error: float = 0.0
    emotion_optimizer: Any = None
    last_cycle_time: float = 0.001
    current_episode: int = 1
    current_step: int = 1

# Import all processes
from src.processes.p1_perception import perception
from src.processes.p2_belief_update import update_belief
from src.processes.p3_emotion_calc import calculate_emotions
from src.processes.p5_adjust_exploration import adjust_exploration
from src.processes.p6_action_select import select_action
from src.processes.p7_execution import execute_action
from src.processes.p8_consequence import record_consequences

def test_bulk_migration():
    # 1. Setup Mock Env
    mock_env = MagicMock()
    # Mock sequence of observations for 2 steps (Initial -> After Action)
    mock_env.get_observation.side_effect = [
        {'agent_pos': (0, 0), 'step_count': 0}, # P1
        {'agent_pos': (0, 1), 'step_count': 1}, # P7 (legacy update)
        {'agent_pos': (0, 1), 'step_count': 1}  # P8 or Next Cycle
    ]
    mock_env.perform_action.return_value = -0.1 # Reward
    
    adapter = EnvironmentAdapter(mock_env)
    
    # 2. Setup Context
    global_ctx = GlobalContext(
        initial_needs=[0.5], initial_emotions=[0.0],
        total_episodes=1, max_steps=100, seed=42,
        switch_locations={'S1': (5,5)},
        initial_exploration_rate=0.5,
        exploration_decay=0.99,
        emotional_boost_factor=0.1,
        min_exploration=0.05
    )
    
    domain_ctx = DomainContext(
        N_vector=torch.tensor([0.5]), E_vector=torch.tensor([0.5, 0.5]), # Conf=0.5
        believed_switch_states={'S1': False}, q_table={}, short_term_memory=[], long_term_memory={},
        base_exploration_rate=0.8,
        last_reward={'extrinsic': 0.0} # Must be dict because p7 writes to it
    )
    system_ctx = SystemContext(global_ctx, domain_ctx)
    
    # 3. Setup Engine
    engine = TheusEngine(system_ctx)
    engine.register_process("p1", perception)
    engine.register_process("p2", update_belief)
    engine.register_process("p3", calculate_emotions)
    engine.register_process("p5", adjust_exploration)
    engine.register_process("p6", select_action)
    engine.register_process("p7", execute_action)
    engine.register_process("p8", record_consequences)
    
    # 4. Run Cycle
    print("--- Step 1: Perception ---")
    engine.run_process("p1", env_adapter=adapter, agent_id=0)
    print(f"Obs: {domain_ctx.current_observation}")
    
    print("--- Step 2: Belief ---")
    engine.run_process("p2")
    
    print("--- Step 3: Emotion ---")
    engine.run_process("p3")
    print(f"E_vector: {domain_ctx.E_vector}")
    
    print("--- Step 5: Exploration ---")
    engine.run_process("p5")
    print(f"Exploration Rate: {domain_ctx.current_exploration_rate}")
    
    print("--- Step 6: Action Select ---")
    engine.run_process("p6")
    print(f"Selected Action: {domain_ctx.selected_action}")
    
    print("--- Step 7: Execution ---")
    engine.run_process("p7", env_adapter=adapter, agent_id=0)
    print(f"Last Reward: {domain_ctx.last_reward}")
    print(f"Current Obs (after P7): {domain_ctx.current_observation}")
    
    print("--- Step 8: Learn ---")
    engine.run_process("p8")
    print(f"Q-Table size: {len(domain_ctx.q_table)}")
    print(f"Memory size: {len(domain_ctx.short_term_memory)}")
    
    # Assertions
    assert len(domain_ctx.short_term_memory) == 1
    assert len(domain_ctx.q_table) > 0 # Should learn something
    
    # Check Logic Correctness:
    # 1. Base rate MUST decay
    assert domain_ctx.base_exploration_rate < 0.8
    # 2. Current rate accounts for boost (0.8*0.995 + 0.5*0.5 ~ 1.046)
    assert domain_ctx.current_exploration_rate > 0.8 
    
    print(">>> BULK MIGRATION TEST PASSED! <<<")

if __name__ == "__main__":
    test_bulk_migration()
