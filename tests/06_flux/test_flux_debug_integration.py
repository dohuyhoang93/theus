
"""
Integration Test: Flux Debug Logging
Verifies that the Rust WorkflowEngine correctly emits [FLUX-DEBUG] logs to stderr 
when invoked with debug=True from Python, and suppresses them when debug=False.
"""

import pytest
import os
import tempfile
from theus import TheusEngine, process

# Mock Process for the workflow
@process(outputs=[])
def p_noop(ctx):
    pass

@pytest.mark.asyncio
async def test_flux_debug_logging_integration(capfd):
    """
    Integration test verifying that debug=True triggers Rust [FLUX-DEBUG] logs.
    Uses capfd (Capture File Descriptor) to ensure we catch low-level Rust stderr output.
    """
    # 1. Setup Engine
    engine = TheusEngine()
    engine.register(p_noop)
    
    # 2. Create minimal workflow
    yaml_content = """
steps:
  - process: "p_noop"
"""
    
    # safe temp file creation
    fd, yaml_path = tempfile.mkstemp(suffix=".yaml", text=True)
    os.close(fd) # Close handle so we can write/read cleanly
    
    try:
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        # --- TEST CASE 1: Debug=True ---
        # Should produce logs in stderr
        await engine.execute_workflow(yaml_path, debug=True)
        
        # Capture output
        out, err = capfd.readouterr()
        
        # Verify Rust logs exist
        assert "[FLUX-DEBUG]" in err, "Rust debug logs missing from stderr when debug=True"
        assert "Parsed 1 top-level steps" in err
        assert "FSM State: Pending -> Running" in err
        
        # --- TEST CASE 2: Debug=False ---
        # Should NOT produce logs
        await engine.execute_workflow(yaml_path, debug=False)
        
        # Capture output again
        out, err = capfd.readouterr()
        
        # Verify logs are absent
        assert "[FLUX-DEBUG]" not in err, "Rust debug logs present in stderr when debug=False"

    finally:
        # Cleanup
        if os.path.exists(yaml_path):
            os.remove(yaml_path)
