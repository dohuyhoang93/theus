import time
import threading
import pytest
from theus import TheusEngine, process
from theus.orchestrator import ThreadExecutor, SignalBus, WorkflowManager
from theus.context import BaseSystemContext

# Mock Context
class MockSystem(BaseSystemContext):
    def __init__(self):
        self.global_ctx = object()
        self.domain_ctx = object()

# Define Slow Process
@process(inputs=[], outputs=[])
def p_heavy_job(ctx):
    time.sleep(0.5)
    return "DONE"

def test_simulated_gui_workflow():
    """
    Simulates a GUI Thread clicking a button.
    Verifies that the Main Thread is NOT blocked while the heavy job runs.
    """
    sys = MockSystem()
    engine = TheusEngine(sys)
    engine.register_process("p_heavy_job", p_heavy_job)
    
    scheduler = ThreadExecutor(max_workers=2)
    bus = SignalBus()
    manager = WorkflowManager(engine, scheduler, bus)
    
    # Define Workflow: IDLE -> CMD_CLICK -> WORKING (Run p_heavy_job)
    workflow_def = {
        "states": {
            "IDLE": {"on": {"CMD_CLICK": "WORKING"}},
            "WORKING": {"entry": "p_heavy_job"}
        }
    }
    manager.load_workflow(workflow_def)
    
    # --- GUI INTERACTION ---
    start_time = time.time()
    
    print("[GUI] Clicking Button...")
    manager.process_signal("CMD_CLICK") 
    
    # CHECK: Did it return immediately?
    gui_free_time = time.time()
    dispatch_duration = gui_free_time - start_time
    
    print(f"[GUI] Free to render! (Took only {dispatch_duration:.4f}s to dispatch)")
    assert dispatch_duration < 0.1, f"GUI Blocked! Dispatch took {dispatch_duration}s"
    
    # --- BACKGROUND WORK ---
    # Now we wait for the actual work to finish (just to be clean)
    scheduler.shutdown(wait=True)
    
    total_duration = time.time() - start_time
    print(f"[BG] Job Finished. Total time: {total_duration:.4f}s")
    
    assert total_duration >= 0.5, "Job finished too fast! Did it actually run?"
