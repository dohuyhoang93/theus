import pytest
from theus.contracts import OutboxMsg
from theus.engine import TheusEngine

# TDD: Outbox Intent

def test_outbox_does_not_execute_immediately():
    engine = TheusEngine()
    
    executed = []
    def mock_sender(msg):
        executed.append(msg)
        
    engine.attach_worker(mock_sender)
    
    # Process runs
    with engine.transaction() as tx:
        tx.outbox.add(OutboxMsg("send_mail", {"user": "test"}))
        assert len(executed) == 0 # NOT yet
        
    # After commit -> Worker picks up
    engine.process_outbox()
    assert len(executed) == 1
