import os
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
    print("\n[Main] Attempting external mutation...")
    try:
        with engine.edit() as ctx:
            ctx.domain_ctx.counter = 100
        print(f"[Main] Counter updated safely to: {system.domain_ctx.counter}")
    except Exception as e:
        print(f"[Main] Error during mutation: {e}")

if __name__ == "__main__":
    main()
