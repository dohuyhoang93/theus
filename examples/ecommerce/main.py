# === THEUS V3.0 FLUX DEMO ===
import sys
import logging
import os
import time

# --- ANSI COLORS ---
class Color:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Configure Logging
logging.basicConfig(level=logging.INFO, format=f'{Color.BLUE}%(message)s{Color.RESET}')

from theus import TheusEngine
from theus.config import ConfigFactory

# Import Context & Processes
from src.context import DemoSystemContext
from src.processes import * 

def main():
    basedir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(basedir, "workflows", "workflow.yaml")
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")

    print(f"\n{Color.BOLD}=== THEUS V3 FLUX DEMO ==={Color.RESET}")
    print(f"{Color.YELLOW}Architecture: Rust Flux Engine + Pure POP Processes{Color.RESET}")
    print("---------------------------------------")
    
    # 1. Init Data Context
    sys_ctx = DemoSystemContext()
    
    # 2. Loading Audit Policy
    print("Loading Audit Policy...")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    # 3. Init Engine
    print("Initializing TheusEngine (V3)...")
    engine = TheusEngine(sys_ctx, strict_mode=True, audit_recipe=recipe)
    
    # 4. Register Processes
    processes_path = os.path.join(basedir, "src", "processes")
    engine.scan_and_register(processes_path)
    
    # 4.5 Seed Data
    with engine.transaction() as tx:
        tx.update(data={"domain": {
            "order_request": {"id": "ORD-001", "items": ["Laptop"], "total": 1500.0},
            "orders": [],
            "balance": 0.0,
            "processed_orders": []
        }})
    
    # 5. Execute Workflow (Flux)
    print(f"Executing Workflow: {workflow_path}")
    try:
        # V3: Engine runs workflow directly (Blocking)
        engine.execute_workflow(workflow_path)
        print(f"\n{Color.GREEN}✨ Workflow Completed Successfully!{Color.RESET}")
    except Exception as e:
        print(f"\n{Color.RED}❌ Workflow Execution Failed: {e}{Color.RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
