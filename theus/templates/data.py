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

@process(inputs=[], outputs=[])
def save_checkpoint_placeholder(ctx: DemoSystemContext):
    print("   [save_checkpoint] Saving system state...")
    return "Saved"

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

TEMPLATE_WORKFLOW = """name: "Theus V3 Flux Workflow"
description: "Declarative Workflow using Theus Flux Engine (Rust Core)."

# FLUX Definition (Theus V3)
# Instead of Python FSM states, we manage control flow declaratively.

steps:
  - process: p_init
    
  # Example Loop
  - flux: while
    condition: "domain.processed_count < 50"
    do:
       - process: p_process
         
       # Example Conditional
       - flux: if
         condition: "domain.processed_count % 20 == 0"
         then:
           - process: save_checkpoint_placeholder
    
  - process: p_finalize
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

TEMPLATE_MAIN = """# === THEUS V3.0 FLUX DEMO ===
import sys
import logging
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

from theus import TheusEngine
from theus.config import ConfigFactory

# Import Context & Processes
from src.context import DemoSystemContext
from src.processes import * 

def main():
    basedir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(basedir, "workflows", "workflow.yaml")
    audit_path = os.path.join(basedir, "specs", "audit_recipe.yaml")

    print(f"\\n{Color.BOLD}=== THEUS V3 FLUX DEMO ==={Color.RESET}")
    print(f"{Color.YELLOW}Architecture: Rust Flux Engine + Pure POP Processes{Color.RESET}")
    print("---------------------------------------")
    
    # 1. Init Data Context
    sys_ctx = DemoSystemContext()
    
    # 2. Loading Audit Policy
    print(f"Loading Audit Policy...")
    recipe = ConfigFactory.load_recipe(audit_path)
    
    # 3. Init Engine
    print(f"Initializing TheusEngine (V3)...")
    engine = TheusEngine(sys_ctx, strict_mode=True, audit_recipe=recipe)
    
    # 4. Register Processes
    processes_path = os.path.join(basedir, "src", "processes")
    engine.scan_and_register(processes_path)
    
    # 5. Execute Workflow (Flux)
    print(f"Executing Workflow: {workflow_path}")
    try:
        # V3: Engine runs workflow directly (Blocking)
        engine.execute_workflow(workflow_path)
        print(f"\\n{Color.GREEN}✨ Workflow Completed Successfully!{Color.RESET}")
    except Exception as e:
        print(f"\\n{Color.RED}❌ Workflow Execution Failed: {e}{Color.RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
"""

# --- HYBRID TEMPLATE (FSM + PIPELINE) ---

TEMPLATE_PROCESS_PIPELINE = """from theus import process
import time
import random

# --- PURE PYTHON LOGIC (The Pipeline) ---
# These functions are NOT processes. They are internal logic steps.
# This avoids "Nested Workflow" overhead and Deadlocks.

def stage_1_perception(data):
    print("      [1/3] Perception: Scanning data...")
    return f"{data}_scanned"

def stage_2_cognition(data):
    print("      [2/3] Cognition: Thinking hard...")
    time.sleep(0.2)
    if random.random() < 0.1:
        return None, "Confusion"
    return f"{data}_processed", None

def stage_3_action(ctx, result):
    print(f"      [3/3] Action: Committing '{result}' to Domain.")
    ctx.domain_ctx.items.append(result)

# --- THE PROCESS WRAPPER ---
# The Engine sees only this SINGLE process.
# But internally, it executes a complex pipeline.

@process(inputs=[], outputs=['domain_ctx.status'])
def p_init(ctx):
    print("   [Init] System Initialization...")
    ctx.domain_ctx.status = "READY"
    return "Initialized"

@process(inputs=[], outputs=['domain_ctx.status'])
def p_finalize(ctx):
    print("   [Finalize] Cleaning up resources...")
    return "Finalized"

@process(inputs=[], outputs=[])
def save_checkpoint_placeholder(ctx):
    print("   [Checkpoint] Saving snapshot...")
    return "Saved"
    
@process(
    inputs=['domain_ctx.status'],
    outputs=['domain_ctx.items', 'domain_ctx.status', 'domain_ctx.processed_count'],
    side_effects=['I/O', 'Compute']
)
def p_run_pipeline(ctx):
    print(f"   [Pipeline] Starting Complex Logic Chain...")
    
    # 1. Fetch
    raw_input = f"Input_{ctx.domain_ctx.processed_count}"
    
    # 2. Pipeline Execution (Local Python Calls)
    percept = stage_1_perception(raw_input)
    result, err = stage_2_cognition(percept)
    
    if err:
        print(f"   [Pipeline] Error detected: {err}")
        ctx.domain_ctx.status = "ERROR" # Reuse 'status' as 'state' for demo simplicity
        return "Pipeline Failed"
        
    stage_3_action(ctx, result)
    
    # 3. Update State
    ctx.domain_ctx.processed_count += 1
    if ctx.domain_ctx.processed_count >= 5:
        ctx.domain_ctx.status = "DONE"
        
    return "Pipeline Success"

@process(inputs=[], outputs=['domain_ctx.status'])
def p_recover(ctx):
    print("   [Recovery] Clearing errors and resetting state...")
    time.sleep(0.5)
    ctx.domain_ctx.status = "RUNNING"
    return "Recovered"
"""

TEMPLATE_WORKFLOW_HYBRID = """name: "Hybrid FSM-Pipeline Demo"
description: "Showcases Flux FSM (Outer Loop) + Python Pipeline (Inner Logic)"

# CONCEPT:
# 1. FLUX ENGINE (YAML): Manages High-Level Interactions and State Transitions.
# 2. PYTHON PIPELINE (Code): Manages Complex localized logic chains.

steps:
  - process: p_init
  
  # --- THE FSM LOOP ---
  - flux: while
    condition: "domain.status != 'DONE'"
    do:
       # DISPATCHER: Check State and Route
       
       # Case 1: READY (Start it up)
       - flux: if
         condition: "domain.status == 'READY'"
         then:
           - process: save_checkpoint_placeholder # Reuse placeholder as 'init' step
           # Manually set to RUNNING inside pipeline or init? 
           # Let's assume p_init set it to READY. Use a lambda? No.
           # Just call pipeline. Pipeline handles RUNNING logic.
           
       # Case 2: READY/RUNNING/PROCESSING (Do Work)
       - flux: if
         condition: "domain.status == 'READY' or domain.status == 'PROCESSING'"
         then:
           # Execute the Heavy Pipeline
           # NOTE: This is ONE process call from Engine's perspective.
           - process: p_run_pipeline
           
       # Case 3: ERROR (Handle Failure)
       - flux: if
         condition: "domain.status == 'ERROR'"
         then:
           - process: p_recover

  - process: p_finalize
"""
