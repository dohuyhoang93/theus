# === THEUS V2.1 SHOWCASE DEMO ===
# This application demonstrates the Industrial Grade Capabilities of Theus.

import sys
import logging
import yaml
import threading
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

# Configure Logging (Short & Cleaner)
logging.basicConfig(level=logging.INFO, format=f'{Color.BLUE}%(message)s{Color.RESET}')

from theus import POPEngine
from theus.config import ConfigFactory
from theus.orchestrator import WorkflowManager, SignalBus, ThreadExecutor

# Import our Custom Context & Processes
from src.context import DemoSystemContext
from src.processes import * 

def print_header():
    print(f"\n{Color.BOLD}=== THEUS v2.1 INDUSTRIAL DEMO ==={Color.RESET}")
    print(f"{Color.YELLOW}Architecture: Microkernel + FSM + ThreadPool{Color.RESET}")
    print("---------------------------------------")

def print_menu():
    print(f"\n{Color.BOLD}COMMANDS:{Color.RESET}")
    print(f"  {Color.GREEN}start{Color.RESET}  : Run the full Hybrid Workflow (State + Chain).")
    print(f"  {Color.RED}hack{Color.RESET}   : Attempt Unsafe Context Mutation (Security Demo).")
    print(f"  {Color.RED}crash{Color.RESET}  : Trigger Process Failure (Resilience Demo).")
    print(f"  {Color.YELLOW}reset{Color.RESET}  : Reset Logic (Manual FSM Reset).")
    print(f"  {Color.BLUE}status{Color.RESET} : Check Internal State.")
    print(f"  {Color.BOLD}quit{Color.RESET}   : Exit.")
    print("---------------------------------------")

def main():
    # 1. Setup basedir
    basedir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(basedir, "specs", "workflow.yaml")
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")

    print_header()
    
    # 2. Add System to Path (if not installed)
    # sys.path.append(...)
    
    # 3. Initialize Context (Pydantic V2)
    sys_ctx = DemoSystemContext()
    
    # 4. Load Audit Recipe
    print(f"1. Loading Audit Policy from {Color.BOLD}audit_recipe.yaml{Color.RESET}...")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    # 5. Initialize Engine (Microkernel)
    print(f"2. Initializing POPEngine (Strict Mode: {Color.GREEN}ON{Color.RESET})...")
    engine = POPEngine(sys_ctx, strict_mode=True, audit_recipe=recipe)
    
    # 6. Register Processes (Auto-Discovery in Real App, Manual here for Clarity)
    from src.processes.chain import p_init, p_process, p_finalize
    from src.processes.stress import p_unsafe_write, p_crash_test, p_transaction_test
    
    engine.register_process("p_init", p_init)
    engine.register_process("p_process", p_process)
    engine.register_process("p_finalize", p_finalize)
    engine.register_process("p_unsafe_write", p_unsafe_write)
    engine.register_process("p_crash_test", p_crash_test)
    engine.register_process("p_transaction_test", p_transaction_test)
    
    # 7. Initialize Orchestrator
    bus = SignalBus()
    scheduler = ThreadExecutor(max_workers=2)
    manager = WorkflowManager(engine, scheduler, bus)
    
    # 8. Load Workflow
    print("3. Loading Workflow FSM...")
    with open(workflow_path, 'r') as f:
        wf_def = yaml.safe_load(f)
    manager.load_workflow(wf_def)
    
    # 9. Start Main Loop (GUI Simulation)
    print_menu()
    
    running = True
    while running:
        try:
            cmd = input(f"\n{Color.BOLD}theus>{Color.RESET} ").strip().lower()
            
            if cmd == 'quit':
                running = False
                print("Exiting...")
            
            elif cmd == 'start':
                print(f"{Color.GREEN}▶ Triggering Workflow...{Color.RESET}")
                bus.emit("CMD_START")
                
            elif cmd == 'reset':
                bus.emit("CMD_RESET")
                print("Reset signal sent.")

            elif cmd == 'hack':
                 print(f"\n{Color.YELLOW}[SECURITY DEMO] Attempting Unsafe Write...{Color.RESET}")
                 print(f"   Current Status: '{sys_ctx.domain_ctx.status}'")
                 bus.emit("CMD_HACK")
                 
                 time.sleep(0.5) # Wait for async execution
                 
                 final_status = sys_ctx.domain_ctx.status
                 if final_status == "HACKED":
                     print(f"{Color.RED}❌ FAILED! Context was Hacked!{Color.RESET}")
                 else:
                     print(f"{Color.GREEN}✅ BLOCKED! Theus ContextGuard prevented the unauthorized write.{Color.RESET}")
                     
            elif cmd == 'crash':
                 print(f"\n{Color.YELLOW}[RESILIENCE DEMO] Triggering Crash...{Color.RESET}")
                 bus.emit("CMD_CRASH")
                 time.sleep(0.5)
                 print(f"{Color.GREEN}✅ SYSTEM ALIVE! Main Loop continues despite Process Crash.{Color.RESET}")

            elif cmd == 'rollback':
                 print(f"\n{Color.YELLOW}[TRANSACTION DEMO] Testing Rollback...{Color.RESET}")
                 print(f"   Original Count: {sys_ctx.domain_ctx.processed_count}")
                 bus.emit("CMD_ROLLBACK")
                 time.sleep(0.8) # Wait for crash
                 final_count = sys_ctx.domain_ctx.processed_count
                 if final_count == 9999:
                     print(f"{Color.RED}❌ FAILED! Dirty Write Persisted! (Count=9999){Color.RESET}")
                 else:
                     print(f"{Color.GREEN}✅ PASSED! Value Rolled Back to {final_count} (Dirty Write Discarded).{Color.RESET}")

            elif cmd == 'status':
                state = manager.fsm.get_current_state()
                data_status = sys_ctx.domain_ctx.status
                print(f"   [FSM State] : {Color.BLUE}{state}{Color.RESET}")
                print(f"   [Data Status] : {Color.GREEN if data_status=='SUCCESS' else Color.YELLOW}{data_status}{Color.RESET}")
                
            # Process Signals (Async Simulation)
            while not bus.empty():
                sig = bus.get(block=False)
                manager.process_signal(sig)
                
        except KeyboardInterrupt:
            running = False
            print("\nForce Quit.")
        except Exception as e:
            print(f"{Color.RED}Error: {e}{Color.RESET}")

if __name__ == "__main__":
    main()
