"""
Test Write Timeout: Deadlock Prevention.
TDD - Tests written BEFORE implementation.

Per MIGRATION_AUDIT.md:
- Write dùng RwLock có timeout. Engine sẽ giết process nào giữ lock quá lâu.
"""
import pytest
import threading
import time


class TestWriteTimeout:
    """Test Write Timeout mechanism for deadlock prevention."""

    def test_transaction_has_timeout_param(self):
        """Transaction should accept write_timeout parameter."""
        from theus_core import Transaction
        
        # Should be able to create with timeout
        tx = Transaction(write_timeout_ms=1000)
        assert tx.write_timeout_ms == 1000

    def test_write_timeout_default(self):
        """Default write timeout should be reasonable (e.g., 5000ms)."""
        from theus_core import Transaction
        
        tx = Transaction()
        assert tx.write_timeout_ms >= 1000  # At least 1 second
        assert tx.write_timeout_ms <= 30000  # At most 30 seconds

    def test_write_timeout_triggers_on_long_hold(self):
        """Write that holds lock too long should be terminated."""
        from theus_core import TheusEngine, WriteTimeoutError
        
        engine = TheusEngine()
        
        # Simulate long-running write that exceeds timeout
        def slow_writer():
            with engine.transaction(write_timeout_ms=100) as tx:
                time.sleep(0.5)  # Hold lock for 500ms
                tx.update({"key": "value"})  # Should fail
        
        with pytest.raises(WriteTimeoutError, match="timed out"):
            slow_writer()

    def test_concurrent_writes_with_timeout(self):
        """Concurrent writes should not deadlock due to timeout."""
        from theus_core import TheusEngine
        
        engine = TheusEngine()
        results = []
        errors = []
        
        def writer(thread_id):
            try:
                with engine.transaction(write_timeout_ms=500) as tx:
                    # Simulate some work
                    time.sleep(0.1)
                    tx.update({f"key_{thread_id}": thread_id})
                results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, e))
        
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3)  # Should complete within 3 seconds
        elapsed = time.time() - start
        
        # At least some should succeed
        assert len(results) + len(errors) == 5
        
        # Should not take forever (deadlock prevention)
        assert elapsed < 3.0, f"Possible deadlock, took {elapsed}s"

    def test_read_is_lock_free(self):
        """Read operations should never timeout (lock-free)."""
        from theus_core import TheusEngine
        
        engine = TheusEngine()
        
        # Setup initial state
        with engine.transaction() as tx:
            tx.update({"key": "value"})
        
        def reader():
            # Read should always succeed instantly
            state = engine.state
            return state.data.get("key")
        
        # Start a long writer
        def slow_writer():
            with engine.transaction(write_timeout_ms=2000) as tx:
                time.sleep(1)  # Hold write lock
                tx.update({"key": "new_value"})
        
        writer_thread = threading.Thread(target=slow_writer)
        writer_thread.start()
        
        # Reader should not be blocked by writer
        time.sleep(0.1)  # Let writer start
        
        start = time.time()
        result = reader()  # Should return immediately
        elapsed = time.time() - start
        
        assert result == "value"
        assert elapsed < 0.1, f"Read was blocked: {elapsed}s"
        
        writer_thread.join()

    def test_timeout_rollback(self):
        """Timed-out transaction should be rolled back."""
        from theus_core import TheusEngine, WriteTimeoutError
        
        engine = TheusEngine()
        
        # Setup initial state
        with engine.transaction() as tx:
            tx.update({"key": "original"})
        
        # Attempt long write that will timeout
        try:
            with engine.transaction(write_timeout_ms=100) as tx:
                tx.update({"key": "modified"})
                time.sleep(0.5)  # Trigger timeout
        except WriteTimeoutError:
            pass
        
        # State should be unchanged (rolled back)
        assert engine.state.data.get("key") == "original"
