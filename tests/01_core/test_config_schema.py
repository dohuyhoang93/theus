import pytest
from theus.config import ConfigLoader, SchemaViolationError

# TDD: Serde-based strict schema validation

def test_config_loader_rejects_unknown_fields():
    yaml_content = """
    context:
      global:
        timeout: 100
      unknown_field: "hacker"
    """
    with pytest.raises(SchemaViolationError):
        ConfigLoader.load_from_string(yaml_content)

def test_config_loader_enforces_types():
    yaml_content = """
    context:
      global:
        timeout: "not_an_int" 
    """
    with pytest.raises(SchemaViolationError):
        ConfigLoader.load_from_string(yaml_content)
