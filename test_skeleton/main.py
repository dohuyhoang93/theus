# === THEUS V2.1 SHOWCASE DEMO ===
import sys
import logging
import yaml
import threading
import os
import time
import queue

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
from theus.orchestrator import WorkflowManager, SignalBus, ThreadExecutor

# Import Context & Processes
from src.context import DemoSystemContext
from src.processes import * 

def print_header():
    print(f"\n{Color.BOLD}=== THEUS v2.1 INDUSTRIAL DEMO ==={Color.RESET}")
    print(f"{Color.YELLOW}Architecture: Microkernel + FSM + ThreadPool{Color.RESET}")
    print("---------------------------------------")

def print_menu():
    print(f"\n{Color.BOLD}COMMANDS:{Color.RESET}")
    print(f"  {Color.GREEN}start{Color.RESET}  : Run Workflow.")
    print(f"  {Color.RED}hack{Color.RESET}   : Security Demo.")
    print(f"  {Color.RED}crash{Color.RESET}  : Resilience Demo.")
    print(f"  {Color.BLUE}rollback{Color.RESET}: Transaction Demo.")
    print(f"  {Color.YELLOW}reset{Color.RESET}  : Reset Logic.")
    print(f"  {Color.BLUE}status{Color.RESET} : Check State.")
    print(f"  {Color.BOLD}quit{Color.RESET}   : Exit.")

def orchestrator_loop(manager, bus, stop_event):
    """Background thread to process signals so UI doesn't block."""
    while not stop_event.is_set():
        try:
            # Blocking get with timeout allows checking stop_event periodically
            signal = bus.get(block=True, timeout=0.1)
            manager.process_signal(signal)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"{Color.RED}Orchestrator Error: {e}{Color.RESET}")

def main():
    basedir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(basedir, "workflows", "workflow.yaml")
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")

    print_header()
    sys_ctx = DemoSystemContext()
    
    print("1. Loading Audit Policy...")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    # 2. Start (Theus V2)
    # -------------------
    # This loop simulates the application runtime.
    # In production, this might be an Infinite Loop or a Web Scraper Trigger.
    
    # Init Engine
    print("2. Initializing TheusEngine...")
    engine = TheusEngine(sys_ctx, strict_mode=True, audit_recipe=recipe)
    
    # Auto-discover and register all @process functions
    processes_path = os.path.join(basedir, "src", "processes")
    engine.scan_and_register(processes_path)
    
    # Orchestrator
    scheduler = ThreadExecutor(max_workers=2)
    bus = SignalBus()
    manager = WorkflowManager(engine, scheduler, bus)
    
    print("3. Loading Workflow FSM...")
    with open(workflow_path, 'r') as f:
        wf_def = yaml.safe_load(f)
    manager.load_workflow(wf_def)
    
    # --- Start Background Orchestrator ---
    stop_event = threading.Event()
    orchestrator_thread = threading.Thread(
        target=orchestrator_loop, 
        args=(manager, bus, stop_event),
        daemon=True
    )
    orchestrator_thread.start()

    print_menu()
    
    running = True
    while running:
        try:
            # Input is blocking, but Orchestrator is now in background!
            cmd = input(f"\n{Color.BOLD}theus>{Color.RESET} ").strip().lower()
            
            if cmd == 'quit':
                running = False
            elif cmd == 'start':
                print(f"{Color.GREEN}▶ Triggering Workflow...{Color.RESET}")
                bus.emit("CMD_START")
            elif cmd == 'reset':
                bus.emit("CMD_RESET")
            elif cmd == 'hack':
                 print(f"\n{Color.YELLOW}[SECURITY DEMO] Attempting Unsafe Write...{Color.RESET}")
                 bus.emit("CMD_HACK")
                 # Sleep briefly to allow logs to appear before next prompt
                 time.sleep(0.2) 
            elif cmd == 'crash':
                 print(f"\n{Color.YELLOW}[RESILIENCE DEMO] Triggering Crash...{Color.RESET}")
                 bus.emit("CMD_CRASH")
                 time.sleep(0.2)
            elif cmd == 'rollback':
                print(f"\n{Color.YELLOW}[TRANSACTION DEMO] Testing Rollback...{Color.RESET}")
                orig_count = sys_ctx.domain_ctx.processed_count
                print(f"   Original Count: {orig_count}")
                bus.emit("CMD_ROLLBACK")
                
                # Check result after a delay
                time.sleep(1.5) 
                
                final_count = sys_ctx.domain_ctx.processed_count
                if final_count == 9999:
                     print(f"{Color.RED}❌ FAILED! Dirty Write Persisted! (Count=9999){Color.RESET}")
                elif final_count == orig_count:
                     print(f"{Color.GREEN}✅ PASSED! Value Rolled Back to {final_count}.{Color.RESET}")
                else:
                     print(f"{Color.RED}❌ FAILED! Value Mismatch! Expected {orig_count}, Got {final_count}{Color.RESET}")

            elif cmd == 'status':
                state = manager.fsm.get_current_state()
                data_status = sys_ctx.domain_ctx.status
                print(f"   [FSM]: {Color.BLUE}{state}{Color.RESET} | [Data]: {data_status}")
                
        except KeyboardInterrupt:
            running = False
        except Exception as e:
            print(f"{Color.RED}Error: {e}{Color.RESET}")
    
    # Cleanup
    stop_event.set()
    orchestrator_thread.join(timeout=1.0)
    scheduler.shutdown()
    print("Goodbye!")

if __name__ == "__main__":
    main()
