import pytest
import time
import yaml
from theus import POPEngine
from theus.orchestrator import ThreadExecutor, SignalBus, WorkflowManager
from src.context import DemoSystemContext
from src.processes.chain import p_init, p_process, p_finalize

def test_hybrid_flow_headless():
    # 1. Init
    sys = DemoSystemContext()
    engine = POPEngine(sys, strict_mode=True)
    engine.register_process("p_init", p_init)
    engine.register_process("p_process", p_process)
    engine.register_process("p_finalize", p_finalize)
    
    scheduler = ThreadExecutor(max_workers=2)
    bus = SignalBus()
    manager = WorkflowManager(engine, scheduler, bus)
    
    # 2. Load YAML (Quote "on" to avoid boolean parsing)
    yaml_str = """
    states:
      IDLE:
        "on":
          CMD_START: PROCESSING
      PROCESSING:
        entry:
          - p_init
          - p_process
          - p_finalize
        "on":
          CMD_RESET: IDLE
    """
    manager.load_workflow(yaml.safe_load(yaml_str))
    
    assert manager.fsm.get_current_state() == "IDLE"
    
    # 3. Trigger
    print("Triggering CMD_START")
    manager.process_signal("CMD_START")
    
    # 4. Check State
    assert manager.fsm.get_current_state() == "PROCESSING"
    
    # 5. Wait for Chain
    time.sleep(2.5) # Wait for 3 steps (0.5 + 1.0 + overhead)
    
    # 6. Check Data
    print(f"Items: {sys.domain_ctx.items}")
    print(f"Status: {sys.domain_ctx.status}")
    
    assert len(sys.domain_ctx.items) == 3
    assert sys.domain_ctx.status == "SUCCESS", f"Status is {sys.domain_ctx.status}"
    
    scheduler.shutdown()
