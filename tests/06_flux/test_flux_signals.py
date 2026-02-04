
"""
Test Flux DSL: flux: if (Signals)
Tests the signal handling capabilities in Flux workflows.
"""

import pytest
from theus_core import WorkflowEngine

class TestFluxSignals:
    """Test Flux DSL signal interaction."""

    def test_signal_get_behavior(self):
        """
        Verify that flux: if can access signals via signal.get().
        NOTE: 'signal' in context must be a Dict, not SignalHub object.
        """
        yaml_content = """
steps:
  - flux: if
    condition: "signal.get('cmd_stop') == 'True'"
    then:
      - process: stop_triggered
    else:
      - process: continued
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        
        # Case 1: Signal matches
        ctx_true = {"signal": {"cmd_stop": "True"}}
        executed_true = []
        engine.execute(ctx_true, lambda n: executed_true.append(n))
        assert executed_true == ["stop_triggered"]

        # Case 2: Signal doesn't match
        ctx_false = {"signal": {"cmd_stop": "False"}}
        executed_false = []
        engine.execute(ctx_false, lambda n: executed_false.append(n))
        assert executed_false == ["continued"]
        
        # Case 3: Signal key missing (default None)
        ctx_empty = {"signal": {}}
        executed_empty = []
        engine.execute(ctx_empty, lambda n: executed_empty.append(n))
        assert executed_empty == ["continued"]

    def test_dynamic_signal_update_in_loop(self):
        """
        Verify that Flux sees signal updates made by processes during execution.
        This confirms 'Live Signal' behavior via shared dictionary mutation.
        """
        yaml_content = """
steps:
  - flux: while
    condition: "signal.get('stop') != 'True'"
    do:
      - process: trigger_signal
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        
        # Shared signal dict
        signals = {"stop": "False"}
        ctx = {"signal": signals}
        
        executed_steps = []
        
        def executor(name):
            executed_steps.append(name)
            if name == "trigger_signal":
                # Simulate external signal arrival (or process updating it)
                signals["stop"] = "True"

        # Should run once, update signal, then exit loop
        engine.execute(ctx, executor)
        
        assert len(executed_steps) == 1
        assert signals["stop"] == "True"

    def test_signal_hub_object_fails(self):
        """
        Verify that passing a raw SignalHub object (Rust) fails.
        This documents the limitation: signals must be a Dict snapshot.
        """
        from theus import SignalHub
        
        yaml_content = """
steps:
  - flux: if
    condition: "signal.get('any') == 'True'"
    then:
      - process: no_op
"""
        engine = WorkflowEngine(yaml_content, 100, False)
        
        hub = SignalHub()
        ctx = {"signal": hub}
        
        # Expect AttributeError: 'SignalHub' object has no attribute 'get'
        with pytest.raises(AttributeError, match="has no attribute 'get'"):
            engine.execute(ctx, lambda n: None)
