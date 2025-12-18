import pytest
import time
import yaml
import logging
from theus import POPEngine
from theus.orchestrator import ThreadExecutor, SignalBus, WorkflowManager
from src.context import DemoSystemContext
from src.processes.stress import p_unsafe_write, p_crash_test

# Configure Logging to capture output
logging.basicConfig(level=logging.INFO)

def test_security_violation_hack():
    """
    Test Phase 1: Security Violation (HACK).
    A process tries to write to a field not declared in 'outputs'.
    Expected: System blocks write, raises Exception internally (caught by process or engine).
    Value should NOT change.
    """
    sys = DemoSystemContext()
    engine = POPEngine(sys, strict_mode=True)
    engine.register_process("p_unsafe_write", p_unsafe_write)
    
    scheduler = ThreadExecutor(max_workers=2)
    bus = SignalBus()
    manager = WorkflowManager(engine, scheduler, bus)
    
    # Workflow
    yaml_str = """
    states:
      IDLE:
        "on":
           CMD_HACK: TEST_HACK
      TEST_HACK:
        entry: p_unsafe_write
    """
    manager.load_workflow(yaml.safe_load(yaml_str))
    
    # Trigger
    print("\n--- [TEST] Triggering HACK ---")
    manager.process_signal("CMD_HACK")
    
    assert manager.fsm.get_current_state() == "TEST_HACK"
    
    time.sleep(1.0) # Wait for thread
    
    # CHECK: Did mutation happen?
    current_status = sys.domain_ctx.status
    print(f"Status after HACK attempt: {current_status}")
    
    assert current_status == "READY" # Should remain default
    assert current_status != "HACKED"
    
    scheduler.shutdown()

def test_crash_resilience():
    """
    Test Phase 2: Crash Resilience.
    A process raises an unhandled Exception.
    Expected: Main Thread (Manager) continues running. ThreadPool handles crash.
    """
    sys = DemoSystemContext()
    engine = POPEngine(sys, strict_mode=True)
    engine.register_process("p_crash_test", p_crash_test)
    
    scheduler = ThreadExecutor(max_workers=2)
    bus = SignalBus()
    manager = WorkflowManager(engine, scheduler, bus)
    
    # Workflow
    yaml_str = """
    states:
      IDLE:
        "on":
           CMD_CRASH: TEST_CRASH
      TEST_CRASH:
        entry: p_crash_test
    """
    manager.load_workflow(yaml.safe_load(yaml_str))
    
    print("\n--- [TEST] Triggering CRASH ---")
    manager.process_signal("CMD_CRASH")
    
    time.sleep(1.0)
    
    # Assertion: If we are here, Main Thread didn't crash.
    # We can check if we can still trigger other things?
    assert manager.fsm.get_current_state() == "TEST_CRASH"
    
    scheduler.shutdown()
