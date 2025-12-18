# Standard Templates for 'pop init' (Showcase Edition)

TEMPLATE_ENV = """# Theus SDK Configuration
# 1 = Strict Mode (Crash on Error)
# 0 = Warning Mode (Log Warning)
THEUS_STRICT_MODE=1
"""

TEMPLATE_CONTEXT = """from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
from theus.context import BaseSystemContext

# --- 1. Global (Configuration) ---
class DemoGlobal(BaseModel):
    app_name: str = "Theus V2 Industrial Demo"
    version: str = "0.2.0"
    max_retries: int = 3

# --- 2. Domain (Mutable State) ---
class DemoDomain(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # State flags
    status: str = "IDLE"          # System Status
    processed_count: int = 0      # Logic Counter
    items: List[str] = Field(default_factory=list) # Data Queue
    
    # Error tracking
    # Error tracking (META Zone)
    meta_last_error: Optional[str] = None

# --- 3. System (Root Container) ---
class DemoSystemContext(BaseSystemContext):
    def __init__(self):
        self.global_ctx = DemoGlobal()
        self.domain_ctx = DemoDomain()
"""

TEMPLATE_PROCESS_CHAIN = """import time
from theus import process
from src.context import DemoSystemContext

# Decorator enforces Contract (Input/Output Safety)

@process(
    inputs=[], 
    outputs=['domain.status'],
    side_effects=['I/O']
)
def p_init(ctx: DemoSystemContext):
    print("   [p_init] Initializing System Resources...")
    ctx.domain_ctx.status = "READY"
    time.sleep(0.5) # Simulate IO
    return "Initialized"

@process(
    inputs=['domain.status', 'domain.items', 'domain.processed_count'],
    outputs=['domain.status', 'domain.processed_count', 'domain.items'],
    side_effects=['I/O']
)
def p_process(ctx: DemoSystemContext):
    print(f"   [p_process] Processing Batch (Current: {ctx.domain_ctx.processed_count})...")
    
    # Simulate Work
    ctx.domain_ctx.status = "PROCESSING"
    time.sleep(1.0) # Simulate Heavy Compute
    
    # Logic
    ctx.domain_ctx.processed_count += 10
    ctx.domain_ctx.items.append(f"Batch_{ctx.domain_ctx.processed_count}")
    
    return "Processed"

@process(
    inputs=['domain.status'], 
    outputs=['domain.status'],
    side_effects=['I/O']
)
def p_finalize(ctx: DemoSystemContext):
    print("   [p_finalize] Finalizing and Cleaning up...")
    ctx.domain_ctx.status = "SUCCESS"
    time.sleep(0.5)
    print("\\n   ✨ [WORKFLOW COMPLETE] Press ENTER to continue...", end="", flush=True) 
    return "Done"
"""

TEMPLATE_PROCESS_STRESS = """import time
from theus import process
from src.context import DemoSystemContext

@process(
    inputs=[], 
    outputs=['domain.status'], 
    side_effects=['I/O'],
    errors=['ValueError']
) # Declared correctly
def p_crash_test(ctx: DemoSystemContext):
    print("   [p_crash_test] About to crash...")
    time.sleep(0.5)
    raise ValueError("Simulated Process Crash!")

@process(
    inputs=['domain.processed_count'], 
    outputs=['domain.processed_count'],
    side_effects=['I/O'],
    errors=['RuntimeError']
)
def p_transaction_test(ctx: DemoSystemContext):
    print(f"   [p_transaction_test] ORIGINAL VALUE: {ctx.domain_ctx.processed_count}")
    print("   [p_transaction_test] Writing DIRTY DATA (9999)...")
    ctx.domain_ctx.processed_count = 9999
    time.sleep(0.5)
    print("   [p_transaction_test] Simulating CRASH...")
    raise RuntimeError("Transaction Failure!")

# MALICIOUS PROCESS: Attempts to write 'domain.status' 
# BUT does NOT declare it in outputs!
@process(inputs=[], outputs=[]) 
def p_unsafe_write(ctx: DemoSystemContext):
    print("   [p_unsafe_write] Attempting illegal write to 'status'...")
    # This should trigger ContextGuardViolation in Strict Mode
    ctx.domain_ctx.status = "HACKED"
    return "Malicious"
"""

TEMPLATE_WORKFLOW = """name: "Hybrid Industrial Workflow"
description: "Demonstrates FSM + Linear Chains"

# FSM Definition
states:
  IDLE:
    "on": 
      CMD_START: "PROCESSING" # External Start Signal
      CMD_HACK: "TEST_HACK"   # Security Test
      CMD_CRASH: "TEST_CRASH" # Resilience Test
      CMD_ROLLBACK: "TEST_TRANSACTION" # Transaction Test

  PROCESSING:
    entry: ["p_init", "p_process", "p_finalize"] # Linear Chain
    "on":
       EVT_CHAIN_DONE: "IDLE" # Auto-return when chain finishes
       CMD_RESET: "IDLE"

  TEST_HACK:
    entry: ["p_unsafe_write"]
    "on":
       EVT_CHAIN_DONE: "IDLE"
       EVT_CHAIN_FAIL: "IDLE" # Return even if failed

  TEST_TRANSACTION:
    entry: ["p_transaction_test"]
    "on":
       EVT_CHAIN_DONE: "IDLE"
       EVT_CHAIN_FAIL: "IDLE"

  TEST_CRASH:
    entry: ["p_crash_test"]
    "on":
       EVT_CHAIN_DONE: "IDLE"
       EVT_CHAIN_FAIL: "IDLE"
"""

TEMPLATE_AUDIT_RECIPE = """process_recipes:
  p_process:
    inputs: []
    outputs: []

  p_unsafe_write:
    # No rules needed, ContextGuard catches it before Audit runs.
    # But we define it to act as policy placeholder.
    inputs: []
"""

TEMPLATE_MAIN = """# === THEUS V2.1 SHOWCASE DEMO ===
import sys
import logging
import yaml
import threading
import os
import time

# --- ANSI COLORS ---
class Color:
    BLUE = '\\033[94m'
    GREEN = '\\033[92m'
    YELLOW = '\\033[93m'
    RED = '\\033[91m'
    RESET = '\\033[0m'
    BOLD = '\\033[1m'

# Configure Logging
logging.basicConfig(level=logging.INFO, format=f'{Color.BLUE}%(message)s{Color.RESET}')

from theus import POPEngine
from theus.config import ConfigFactory
from theus.orchestrator import WorkflowManager, SignalBus, ThreadExecutor

# Import Context & Processes
from src.context import DemoSystemContext
from src.processes import * 

def print_header():
    print(f"\\n{Color.BOLD}=== THEUS v2.1 INDUSTRIAL DEMO ==={Color.RESET}")
    print(f"{Color.YELLOW}Architecture: Microkernel + FSM + ThreadPool{Color.RESET}")
    print("---------------------------------------")

def print_menu():
    print(f"\\n{Color.BOLD}COMMANDS:{Color.RESET}")
    print(f"  {Color.GREEN}start{Color.RESET}  : Run Workflow.")
    print(f"  {Color.RED}hack{Color.RESET}   : Security Demo.")
    print(f"  {Color.RED}crash{Color.RESET}  : Resilience Demo.")
    print(f"  {Color.BLUE}rollback{Color.RESET}: Transaction Demo.")
    print(f"  {Color.YELLOW}reset{Color.RESET}  : Reset Logic.")
    print(f"  {Color.BLUE}status{Color.RESET} : Check State.")
    print(f"  {Color.BOLD}quit{Color.RESET}   : Exit.")

def main():
    basedir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(basedir, "specs", "workflow.yaml")
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")

    print_header()
    sys_ctx = DemoSystemContext()
    
    print(f"1. Loading Audit Policy...")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    print(f"2. Initializing POPEngine...")
    engine = POPEngine(sys_ctx, strict_mode=True, audit_recipe=recipe)
    
    # Register Processes
    from src.processes.chain import p_init, p_process, p_finalize
    from src.processes.stress import p_unsafe_write, p_crash_test, p_transaction_test
    
    engine.register_process("p_init", p_init)
    engine.register_process("p_process", p_process)
    engine.register_process("p_finalize", p_finalize)
    engine.register_process("p_unsafe_write", p_unsafe_write)
    engine.register_process("p_crash_test", p_crash_test)
    engine.register_process("p_transaction_test", p_transaction_test)
    
    # Orchestrator
    scheduler = ThreadExecutor(max_workers=2)
    bus = SignalBus()
    manager = WorkflowManager(engine, scheduler, bus)
    
    print("3. Loading Workflow FSM...")
    with open(workflow_path, 'r') as f:
        wf_def = yaml.safe_load(f)
    manager.load_workflow(wf_def)
    
    print_menu()
    
    running = True
    while running:
        try:
            cmd = input(f"\\n{Color.BOLD}theus>{Color.RESET} ").strip().lower()
            
            if cmd == 'quit':
                running = False
            elif cmd == 'start':
                print(f"{Color.GREEN}▶ Triggering Workflow...{Color.RESET}")
                bus.emit("CMD_START")
            elif cmd == 'reset':
                bus.emit("CMD_RESET")
            elif cmd == 'hack':
                 print(f"\\n{Color.YELLOW}[SECURITY DEMO] Attempting Unsafe Write...{Color.RESET}")
                 bus.emit("CMD_HACK")
                 time.sleep(0.5)
                 if sys_ctx.domain_ctx.status == "HACKED":
                     print(f"{Color.RED}❌ FAILED! Hacked!{Color.RESET}")
                 else:
                     print(f"{Color.GREEN}✅ BLOCKED! ContextGuard prevented write.{Color.RESET}")
            elif cmd == 'crash':
                 print(f"\\n{Color.YELLOW}[RESILIENCE DEMO] Triggering Crash...{Color.RESET}")
                 bus.emit("CMD_CRASH")
                 time.sleep(0.5)
                 print(f"{Color.GREEN}✅ SYSTEM ALIVE!{Color.RESET}")
            elif cmd == 'rollback':
                print(f"\\n{Color.YELLOW}[TRANSACTION DEMO] Testing Rollback...{Color.RESET}")
                orig_count = sys_ctx.domain_ctx.processed_count
                print(f"   Original Count: {orig_count}")
                bus.emit("CMD_ROLLBACK")
                time.sleep(1.5) # Wait for Process -> Write -> Sleep -> Crash -> Rollback
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
                
            while not bus.empty():
                manager.process_signal(bus.get(block=False))
                
        except KeyboardInterrupt:
            running = False
        except Exception as e:
            print(f"{Color.RED}Error: {e}{Color.RESET}")

if __name__ == "__main__":
    main()
"""
