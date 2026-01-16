import pytest
from pydantic import BaseModel, ValidationError
from theus import TheusEngine, process, SchemaViolationError

# Define Schema
class ExperimentState(BaseModel):
    # Enforce type and constraints
    episode: int
    score: float
    mode: str = "train"

@pytest.fixture
def engine_with_schema():
    engine = TheusEngine()
    # Note: Schema validates the FINAL STATE, not just the delta
    # So we must initialize state first or ensure defaults
    # Initial state is empty, so we must be careful.
    
    # We set schema.
    # But wait, current state is empty.
    # If we set schema now, does it validate strictly immediately? 
    # No, validation happens on Transaction Commit.
    
    engine.set_schema(ExperimentState)
    return engine

def test_schema_valid_update(engine_with_schema):
    """Verify valid update passes schema check."""
    engine = engine_with_schema
    
    # Init valid state
    with engine.transaction() as txn:
        txn.update(data={
            "episode": 1,
            "score": 0.0,
            "mode": "train"
        })
    
    # Verify state
    assert engine.state.data["episode"] == 1
    assert engine.state.data["score"] == 0.0

def test_schema_violation_wrong_type(engine_with_schema):
    """Verify type error raises SchemaViolationError."""
    engine = engine_with_schema
    
    # First set valid state to pass previous checks if any (new engine per test though)
    # Actually, we rely on atomic commit.
    
    with pytest.raises(SchemaViolationError) as excinfo:
        with engine.transaction() as txn:
            txn.update(data={
                "episode": "not_an_int", # VIOLATION
                "score": 0.0
            })
    
    print(f"Caught expected error: {excinfo.value}")
    assert "Schema Violation" in str(excinfo.value)
    
    # Verify State was NOT updated (Rollback)
    # Should range error or empty
    # Since init failed, it should be empty
    assert len(engine.state.data.keys()) == 0

def test_schema_violation_missing_field(engine_with_schema):
    """Verify missing field raises SchemaViolationError."""
    engine = engine_with_schema
    
    with pytest.raises(SchemaViolationError):
        with engine.transaction() as txn:
            txn.update(data={
                "episode": 1
                # "score" is missing and required
            })

def test_schema_partial_update_on_existingGeneric(engine_with_schema):
    """
    Verify partial update on existing state VALIDATES correctly.
    Theus merges changes, then validates the RESULT.
    """
    engine = engine_with_schema
    
    # 1. Setup Valid State
    with engine.transaction() as txn:
        txn.update(data={"episode": 1, "score": 10.0, "mode": "train"})
        
    assert engine.state.data["score"] == 10.0
    
    # 2. Partial Update (Valid)
    with engine.transaction() as txn:
        txn.update(data={"score": 20.0}) # Should merge with episode=1, mode=train
        
    assert engine.state.data["score"] == 20.0
    assert engine.state.data["episode"] == 1
    
    # 3. Partial Update causing Invalid State
    with pytest.raises(SchemaViolationError):
        with engine.transaction() as txn:
            txn.update(data={"score": "invalid"}) # Type mismatch

if __name__ == "__main__":
    # Manual run for debug
    engine = TheusEngine()
    engine.set_schema(ExperimentState)
    try:
        with engine.transaction() as txn:
            txn.update(data={"episode": 1, "score": 10.0})
        print("Success")
    except Exception as e:
        print(f"Failed: {e}")
