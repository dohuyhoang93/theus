import sys
import os
import torch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataclasses import dataclass
from typing import Any, List, Dict
from theus.context import BaseGlobalContext, BaseDomainContext, BaseSystemContext as SystemContext
from theus import TheusEngine, process

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

# 1. Define a dummy process
@process(inputs=['global_ctx.initial_exploration_rate'], outputs=['domain_ctx.current_exploration_rate'])
def dummy_process(ctx: SystemContext):
    # Logic: Reset exploration rate to base
    base = ctx.global_ctx.initial_exploration_rate
    ctx.domain_ctx.current_exploration_rate = base
    print(f"Process ran. Set exploration to {base}")

def test_pop_arch():
    # 2. Setup Context
    global_ctx = GlobalContext(
        initial_needs=[0.5, 0.5],
        initial_emotions=[0.0, 0.0],
        total_episodes=10,
        max_steps=100,
        seed=42,
        switch_locations={'A': (1,1)}
    )
    
    domain_ctx = DomainContext(
        N_vector=torch.tensor([0.5, 0.5]),
        E_vector=torch.tensor([0.0, 0.0]),
        believed_switch_states={'A': False},
        q_table={},
        short_term_memory=[],
        long_term_memory={}
    )
    
    system_ctx = SystemContext(global_ctx=global_ctx, domain_ctx=domain_ctx)
    
    # 3. Setup Engine
    engine = TheusEngine(system_ctx)
    engine.register_process("test_p1", dummy_process)
    
    # 4. Execute
    print("Before:", system_ctx.domain_ctx.current_exploration_rate)
    system_ctx.domain_ctx.current_exploration_rate = 0.5 # sabotage
    print("Sabotaged:", system_ctx.domain_ctx.current_exploration_rate)
    
    engine.run_process("test_p1")
    
    print("After:", system_ctx.domain_ctx.current_exploration_rate)
    
    assert system_ctx.domain_ctx.current_exploration_rate == 1.0
    print("POP Core Test Passed!")

if __name__ == "__main__":
    test_pop_arch()
