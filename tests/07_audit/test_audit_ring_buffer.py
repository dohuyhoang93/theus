"""
Test Audit Ring Buffer: Append-only logging.
TDD - Tests written BEFORE implementation.

Per MIGRATION_AUDIT.md:
- Audit Log là "Append-Only". Không thể bị xóa/sửa bởi Process.
- System Log (Ring Buffer) - Tốc độ ghi log audit cực nhanh, không block luồng chính.
"""
import pytest


class TestAuditRingBuffer:
    """Test Audit System Ring Buffer."""

    def test_ring_buffer_exists(self):
        """AuditSystem should have ring_buffer property."""
        from theus_core import AuditSystem
        
        audit = AuditSystem()
        assert hasattr(audit, 'ring_buffer') or hasattr(audit, 'get_logs')

    def test_ring_buffer_append_only(self):
        """Ring buffer should be append-only."""
        from theus_core import AuditSystem
        
        audit = AuditSystem(capacity=100)
        
        # Log some entries
        audit.log("event_1", "Process A started")
        audit.log("event_2", "Process B completed")
        
        logs = audit.get_logs()
        assert len(logs) >= 2
        
        # Attempt to modify should fail
        with pytest.raises(Exception):
            audit.clear_logs()  # Should not be allowed

    def test_ring_buffer_capacity(self):
        """Ring buffer should respect capacity limit."""
        from theus_core import AuditSystem
        
        capacity = 10
        audit = AuditSystem(capacity=capacity)
        
        # Add more entries than capacity
        for i in range(20):
            audit.log(f"event_{i}", f"Entry {i}")
        
        logs = audit.get_logs()
        
        # Should only have last 'capacity' entries
        assert len(logs) == capacity
        
        # Oldest entries should be dropped (FIFO)
        first_entry = logs[0]
        assert "event_10" in str(first_entry) or first_entry.key == "event_10"

    def test_ring_buffer_thread_safe(self):
        """Ring buffer writes should be lock-free (non-blocking)."""
        from theus_core import AuditSystem
        import threading
        import time
        
        audit = AuditSystem(capacity=1000)
        errors = []
        
        def writer(thread_id):
            try:
                for i in range(100):
                    audit.log(f"thread_{thread_id}_{i}", f"Message from thread {thread_id}")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start
        
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert audit.get_count_all() == 500
        
        # Should complete quickly (non-blocking)
        assert elapsed < 2.0, f"Ring buffer too slow: {elapsed}s"

    def test_ring_buffer_entry_structure(self):
        """Each entry should have timestamp, key, message."""
        from theus_core import AuditSystem
        
        audit = AuditSystem()
        audit.log("test_key", "test message")
        
        logs = audit.get_logs()
        entry = logs[0]
        
        # Entry should have timestamp
        assert hasattr(entry, 'timestamp') or 'timestamp' in entry
        
        # Entry should have key
        assert hasattr(entry, 'key') or 'key' in entry
        
        # Entry should have message
        assert hasattr(entry, 'message') or 'message' in entry

    def test_ring_buffer_immutable_entries(self):
        """Entries should be immutable after creation."""
        from theus_core import AuditSystem
        
        audit = AuditSystem()
        audit.log("test_key", "original message")
        
        logs = audit.get_logs()
        entry = logs[0]
        
        # Attempt to modify entry
        with pytest.raises((AttributeError, TypeError)):
            entry.message = "modified"
