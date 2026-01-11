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
    outputs=['domain_ctx.status'],
    side_effects=['I/O']
)
def p_init(ctx: DemoSystemContext):
    print("   [p_init] Initializing System Resources...")
    ctx.domain_ctx.status = "READY"
    time.sleep(0.5) # Simulate IO
    return "Initialized"

@process(
    inputs=['domain_ctx.status', 'domain_ctx.items', 'domain_ctx.processed_count'],
    outputs=['domain_ctx.status', 'domain_ctx.processed_count', 'domain_ctx.items'],
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
    inputs=['domain_ctx.status'], 
    outputs=['domain_ctx.status'],
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
    outputs=['domain_ctx.status'], 
    side_effects=['I/O'],
    errors=['ValueError']
) # Declared correctly
def p_crash_test(ctx: DemoSystemContext):
    print("   [p_crash_test] About to crash...")
    time.sleep(0.5)
    raise ValueError("Simulated Process Crash!")

@process(
    inputs=['domain_ctx.processed_count'], 
    outputs=['domain_ctx.processed_count'],
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
    events: 
      CMD_START: "PROCESSING" # External Start Signal
      CMD_HACK: "TEST_HACK"   # Security Test
      CMD_CRASH: "TEST_CRASH" # Resilience Test
      CMD_ROLLBACK: "TEST_TRANSACTION" # Transaction Test

  PROCESSING:
    entry: ["p_init", "p_process", "p_finalize"] # Linear Chain
    events:
       EVT_CHAIN_DONE: "IDLE" # Auto-return when chain finishes
       EVT_CHAIN_FAIL: "IDLE" # Fallback on error
       CMD_RESET: "IDLE"

  TEST_HACK:
    entry: ["p_unsafe_write"]
    events:
       EVT_CHAIN_DONE: "IDLE"
       EVT_CHAIN_FAIL: "IDLE" # Return even if failed

  TEST_TRANSACTION:
    entry: ["p_transaction_test"]
    events:
       EVT_CHAIN_DONE: "IDLE"
       EVT_CHAIN_FAIL: "IDLE"

  TEST_CRASH:
    entry: ["p_crash_test"]
    events:
       EVT_CHAIN_DONE: "IDLE"
       EVT_CHAIN_FAIL: "IDLE"

# --- FLUX EXAMPLES (Advanced Logic) ---
#   COMPLEX_STATE:
#     entry:
#       - flux: run
#         steps:
#           - "p_step1"
#           - flux: if
#             condition: "ctx.domain_ctx.processed_count > 50"
#             then:
#               - "p_step2_high_load"
#             else:
#               - "p_step2_normal"
#           - flux: while
#             condition: "len(ctx.domain_ctx.items) > 0"
#             do:
#               - "p_process_item"
#     events:
#       EVT_CHAIN_DONE: "IDLE"

"""

TEMPLATE_AUDIT_RECIPE = """# ================================================================
# THEUS AUDIT RECIPE (specs/audit_recipe.yaml)
# ================================================================
# This file defines RULES for validating process Inputs/Outputs.
# The Audit Layer acts as an Industrial QA Gate.
#
# --- SEVERITY LEVELS ---
# S (Shutdown)  : Critical. Process halts immediately. System may restart.
# A (Alert)     : Severe. Process fails, workflow stops. Human review needed.
# B (Block)     : Moderate. Transaction rolls back, but workflow can continue.
# C (Caution)   : Minor. Logged as warning. No interruption.
# I (Info)      : Purely informational. For monitoring/metrics.
#
# --- SUPPORTED CONDITIONS (Rust Core) ---
# min      : Value >= limit (numeric)
# max      : Value <= limit (numeric)
# eq       : Value == string (string comparison)
# neq      : Value != string (string comparison)
# min_len  : len(value) >= limit (for list/string)
# max_len  : len(value) <= limit (for list/string)
#
# --- DUAL THRESHOLD MECHANISM ---
# min_threshold : Counter value to START issuing warnings (Yellow Zone).
# max_threshold : Counter value to TRIGGER the action per Level (Red Zone).
# reset_on_success: If true, counter resets to 0 after a successful check.
#
# Example: min_threshold: 2, max_threshold: 5
#   - 0-1 violations: Silent.
#   - 2-4 violations: Warning logged.
#   - 5+  violations: Action triggered (e.g., Block for Level B).
# ================================================================

process_recipes:

  # --- BASIC EXAMPLE (Active) ---
  p_process:
    inputs:
      - field: "domain_ctx.status"
        eq: "READY"               # Must be exactly "READY" to proceed
        level: "B"                # Block if status is wrong
        message: "Process requires status to be READY."
    outputs:
      - field: "domain_ctx.processed_count"
        min: 0                    # Output must be non-negative
        level: "C"                # Just a warning

  p_unsafe_write:
    # No audit rules needed here. ContextGuard catches illegal writes first.
    # This placeholder exists purely for documentation purposes.
    inputs: []
    outputs: []

  # --- ADVANCED EXAMPLES (Commented) ---

  # Example 1: Dual Threshold with Accumulating Counter
  # -------------------------------------------------------
  # p_login_attempt:
  #   inputs:
  #     - field: "domain_ctx.user_id"
  #       min_len: 3              # User ID must be at least 3 chars
  #       level: "B"
  #   outputs:
  #     - field: "domain_ctx.failed_attempts"
  #       max: 5                  # Max 5 failed attempts
  #       level: "A"              # ALERT severity
  #       min_threshold: 3        # Start warning at 3 failures
  #       max_threshold: 5        # Trigger Alert at 5 failures
  #       reset_on_success: false # DO NOT reset on success (accumulate!)
  #       message: "Too many failed login attempts. Account locked."

  # Example 2: Inheritance (Reuse common rules)
  # -------------------------------------------------------
  # _base_financial:             # Prefix '_' for abstract/base template
  #   inputs:
  #     - field: "domain_ctx.amount"
  #       min: 0.01
  #       level: "B"
  #   outputs:
  #     - field: "domain_ctx.balance"
  #       min: 0
  #       level: "A"
  #       message: "Balance cannot go negative!"
  #
  # p_transfer:
  #   inherits: "_base_financial"  # Inherits all input/output rules
  #   side_effects: ["database", "notification"]
  #   errors: ["InsufficientFundsError", "TransferLimitExceeded"]

  # Example 3: Multiple Conditions on Same Field (Range Check)
  # -------------------------------------------------------
  # p_set_age:
  #   inputs:
  #     - field: "domain_ctx.age"
  #       min: 0                  # Rule 1: Must be >= 0
  #       max: 120                # Rule 2: Must be <= 120
  #       level: "B"              # Both share Level B
  #       message: "Age must be between 0 and 120."

  # Example 4: String Length Validation
  # -------------------------------------------------------
  # p_set_username:
  #   inputs:
  #     - field: "domain_ctx.username"
  #       min_len: 3              # At least 3 characters
  #       max_len: 20             # At most 20 characters
  #       level: "B"
  #       message: "Username must be 3-20 characters."

  # Example 5: Not Equal Check (Blacklist)
  # -------------------------------------------------------
  # p_set_status:
  #   inputs:
  #     - field: "domain_ctx.status"
  #       neq: "LOCKED"           # Status must NOT be "LOCKED"
  #       level: "A"
  #       message: "Cannot proceed while status is LOCKED."
"""

TEMPLATE_MAIN = """# === THEUS V2.1 SHOWCASE DEMO ===
import sys
import logging
import yaml
import threading
import os
import time
import queue

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

from theus import TheusEngine
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

def orchestrator_loop(manager, bus, stop_event):
    \"\"\"Background thread to process signals so UI doesn't block.\"\"\"
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
    
    print(f"1. Loading Audit Policy...")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    # 2. Start (Theus V2)
    # -------------------
    # This loop simulates the application runtime.
    # In production, this might be an Infinite Loop or a Web Scraper Trigger.
    
    # Init Engine
    print(f"2. Initializing TheusEngine...")
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
                 # Sleep briefly to allow logs to appear before next prompt
                 time.sleep(0.2) 
            elif cmd == 'crash':
                 print(f"\\n{Color.YELLOW}[RESILIENCE DEMO] Triggering Crash...{Color.RESET}")
                 bus.emit("CMD_CRASH")
                 time.sleep(0.2)
            elif cmd == 'rollback':
                print(f"\\n{Color.YELLOW}[TRANSACTION DEMO] Testing Rollback...{Color.RESET}")
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
"""
