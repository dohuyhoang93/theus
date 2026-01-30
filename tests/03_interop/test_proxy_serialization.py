import pytest
import json
from unittest.mock import MagicMock
from theus_core import SupervisorProxy

try:
    from pydantic import BaseModel, ConfigDict, ValidationError

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


# Fixture for common proxy setup
@pytest.fixture
def proxy_setup():
    mock_tx = MagicMock()
    target = {"a": 1, "b": 2, "nested": {"x": 10}}
    # Signature: SupervisorProxy(target, path, read_only, transaction)
    proxy = SupervisorProxy(target, "domain", False, mock_tx)
    return proxy


def test_json_serialization_behavior(proxy_setup):
    """
    Verify JSON serialization limitations and workarounds.
    Issue 4.3: Proxy is a Mapping, but not a dict, so json.dumps fails natively.
    """
    proxy = proxy_setup

    # 1. Native json.dumps should FAIL (Protocol limitation)
    with pytest.raises(TypeError, match="is not JSON serializable"):
        json.dumps(proxy)

    # 2. Casting to dict should SUCCEED (Shallow copy)
    as_dict = dict(proxy)
    assert type(as_dict) is dict
    assert as_dict["a"] == 1
    assert as_dict["b"] == 2
    # Nested items remain proxies in a simple dict() cast
    assert not isinstance(as_dict["nested"], dict)

    # 3. .to_dict() helper should SUCCEED (Recursive)
    if hasattr(proxy, "to_dict"):
        from_helper = proxy.to_dict()
        assert from_helper == {"a": 1, "b": 2, "nested": {"x": 10}}
        # Now this recursive dict is fully JSON serializable
        json_str = json.dumps(from_helper)
        assert '"x": 10' in json_str


@pytest.mark.skipif(not HAS_PYDANTIC, reason="Pydantic not installed")
def test_pydantic_default_validation_succeeds(proxy_setup):
    """
    Verify that default Pydantic validation now succeeds because
    SupervisorProxy is registered as a Mapping in theus/__init__.py.
    """

    class MyModel(BaseModel):
        a: int
        b: int

    proxy = proxy_setup

    # [v3.1.2] Thanks to Mapping.register(SupervisorProxy), this now works out of the box!
    m = MyModel.model_validate(proxy)
    assert m.a == 1
    assert m.b == 2


@pytest.mark.skipif(not HAS_PYDANTIC, reason="Pydantic not installed")
def test_pydantic_orm_mode_succeeds(proxy_setup):
    """
    Verify that Pydantic ORM Mode (from_attributes=True) works with Proxy.
    This is the official Solution for Issue 4.3.
    """

    class MyModelORM(BaseModel):
        model_config = ConfigDict(from_attributes=True)
        a: int
        b: int

    proxy = proxy_setup

    # Should succeed now
    m = MyModelORM.model_validate(proxy)
    assert m.a == 1
    assert m.b == 2
