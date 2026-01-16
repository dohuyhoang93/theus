"""
Test Meta Zone Ring Buffer: System log for Meta Zone.
TDD - Tests written BEFORE implementation.

Per MIGRATION_AUDIT.md:
- Meta Zone: System Log. Hidden & Protected.
"""
import pytest


class TestMetaRingBuffer:
    """Test Meta Zone Ring Buffer (System Log)."""

    def test_state_has_meta_zone(self):
        """State should have meta zone accessible."""
        from theus_core import State
        
        state = State()
        assert hasattr(state, 'meta') or hasattr(state, 'system_log')

    def test_meta_zone_protected_from_process(self):
        """Meta zone should be hidden from regular processes."""
        from theus_core import ContextGuard
        
        # Create guard with normal inputs (no meta access)
        target = {"meta_log": [], "data": {}}
        guard = ContextGuard(
            target=target,
            inputs=["data"],
            outputs=["data"],
            strict_mode=True
        )
        
        # Attempting to read meta should fail
        with pytest.raises(PermissionError):
            _ = guard.meta_log

    def test_meta_zone_ring_buffer_log(self):
        """Meta zone should have ring buffer for system logs."""
        from theus_core import State
        
        state = State(meta_capacity=100)
        
        # Log system events
        state.log_meta("engine_start", "TheusEngine initialized")
        state.log_meta("process_run", "Process 'step_a' started")
        
        logs = state.get_meta_logs()
        assert len(logs) == 2

    def test_meta_ring_buffer_capacity(self):
        """Meta ring buffer should respect capacity."""
        from theus_core import State
        
        capacity = 10
        state = State(meta_capacity=capacity)
        
        for i in range(20):
            state.log_meta(f"event_{i}", f"Message {i}")
        
        logs = state.get_meta_logs()
        assert len(logs) == capacity

    def test_meta_protected_from_clear(self):
        """Meta logs cannot be cleared by user code."""
        from theus_core import State
        
        state = State()
        state.log_meta("test", "test message")
        
        with pytest.raises(Exception):
            state.clear_meta_logs()

    def test_meta_includes_timestamps(self):
        """Meta log entries should include timestamps."""
        from theus_core import State
        
        state = State()
        state.log_meta("test", "test message")
        
        logs = state.get_meta_logs()
        entry = logs[0]
        
        assert hasattr(entry, 'timestamp') or 'timestamp' in entry

    def test_meta_log_automatic_on_state_update(self):
        """State updates should be automatically logged to meta."""
        from theus_core import State
        
        state = State()
        state2 = state.update(data={"key": "value"})
        
        logs = state2.get_meta_logs()
        
        # Should have logged the update
        assert any("update" in str(log).lower() for log in logs)
