# Standard Templates for 'pop init'

TEMPLATE_ENV = """# Theus SDK Configuration
# 1 = Strict Mode (Crash on Error)
# 0 = Warning Mode (Log Warning)
THEUS_STRICT_MODE=1
"""

TEMPLATE_CONTEXT = """from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
# Theus V2: Using Pydantic for robust type checking.

class GlobalContext(BaseModel):
    \"\"\"Reads-only configuration and constants.\"\"\"
    app_name: str = "My Theus Agent"
    version: str = "0.1.4"

class DomainContext(BaseModel):
    \"\"\"Mutable domain state.\"\"\"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    counter: int = 0
    data: List[str] = Field(default_factory=list)

class SystemContext(BaseModel):
    \"\"\"Root container.\"\"\"
    global_ctx: GlobalContext
    domain_ctx: DomainContext
    is_running: bool = True
    
    # Engine Compatibility: Lock Manager Hook
    _lock_manager: Any = None
    
    def set_lock_manager(self, manager: Any):
        self._lock_manager = manager
"""

TEMPLATE_Hello_PROCESS = """from theus import process
from src.context import SystemContext

@process(
    inputs=['domain.counter', 'domain.data'],
    outputs=['domain.data', 'domain.counter']
)
def hello_world(ctx: SystemContext):
    \"\"\"
    A simple example process.
    \"\"\"
    # Valid Read
    current_val = ctx.domain_ctx.counter
    
    # Mutation (Allowed because specified in outputs)
    ctx.domain_ctx.counter += 1
    ctx.domain_ctx.data.append(f"Hello World #{ctx.domain_ctx.counter}")
    
    print(f"[Process] Hello World! Counter is now {ctx.domain_ctx.counter}")
    return "OK"
"""

TEMPLATE_WORKFLOW = """name: "Main Workflow"
description: "A standard loop for the agent."

steps:
  - p_hello
  - p_hello
  - p_hello
"""

TEMPLATE_MAIN = """import os
import sys
from dotenv import load_dotenv

# Ensure 'src' is in path
sys.path.append(os.path.join(os.getcwd()))

from theus import POPEngine
from theus.config import ConfigFactory
from src.context import SystemContext, GlobalContext, DomainContext

# Import Processes (Explicit Registration)
from src.processes.p_hello import hello_world

def main():
    # 1. Load Environment
    load_dotenv()
    print("--- Initializing Theus Agent ---")
    
    # 2. Setup Context
    system = SystemContext(
        global_ctx=GlobalContext(),
        domain_ctx=DomainContext()
    )
    
    # 3. Load Governance (Audit Recipe)
    # This prevents "State Spaghetti" and enforces logic safety.
    try:
        audit_recipe = ConfigFactory.load_recipe("specs/audit_recipe.yaml")
    except Exception as e:
        print(f"⚠️  Warning: Could not load Audit Recipe: {e}")
        audit_recipe = None

    # 4. Init Engine
    engine = POPEngine(system, audit_recipe=audit_recipe)
    
    # 5. Register Processes
    engine.register_process("p_hello", hello_world)
    
    # 6. Run Workflow
    print("[Main] Running Workflow...")
    engine.run_process("p_hello")
    engine.run_process("p_hello")
    
    # 7. External Mutation Example (via Edit Context)
    print("\\n[Main] Attempting external mutation...")
    try:
        with engine.edit() as ctx:
            ctx.domain_ctx.counter = 100
        print(f"[Main] Counter updated safely to: {system.domain_ctx.counter}")
    except Exception as e:
        print(f"[Main] Error during mutation: {e}")

if __name__ == "__main__":
    main()
"""

TEMPLATE_AUDIT_RECIPE = """# Industrial Audit Rules (The Vault)
process_recipes:
  p_hello:
    inputs:
      - field: domain.counter
        condition: min
        value: 0
        level: S  # Strict Crash if < 0 (Safety)
    outputs:
      - field: domain.counter
        condition: min
        value: 0
        level: A  # Alert if violation (Quality)
      - field: domain.data
        condition: exists
        value: true
        level: S
"""
