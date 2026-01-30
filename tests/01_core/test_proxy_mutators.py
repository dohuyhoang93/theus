import pytest
from unittest.mock import MagicMock
from theus import TheusEngine

# We need to import SupervisorProxy but it's in theus_core.
from theus_core import SupervisorProxy


def test_proxy_mutators_zero_trust():
    print("\n--- Testing Zero Trust Mutators (Update/Pop/Clear) ---")

    # Mock Transaction Object
    # Needs a log_delta method
    mock_tx = MagicMock()
    mock_tx.log_delta = MagicMock()

    # Create a target dict
    target = {"a": 1, "b": 2, "nested": {"x": 10}}

    # Create Proxy with Transaction
    # Signature: SupervisorProxy(target, path, read_only, transaction)
    proxy = SupervisorProxy(target, "test_domain", False, mock_tx)

    print(f"Proxy created: {proxy}")

    # 1. Test .update()
    print("\n1. Testing .update({'a': 100, 'c': 3})")
    proxy.update({"a": 100, "c": 3})

    # Verify Audit Logs
    calls = mock_tx.log_delta.call_args_list
    captured_logs = [(c.args[0], c.args[1], c.args[2]) for c in calls]

    expected_logs = [("test_domain.a", 1, 100), ("test_domain.c", None, 3)]

    for exp in expected_logs:
        assert exp in captured_logs, f"Missing log for: {exp}. Got: {captured_logs}"

    # Clear mocks
    mock_tx.log_delta.reset_mock()

    # 2. Test .pop()
    print("\n2. Testing .pop('b')")
    val = proxy.pop("b")
    assert val == 2

    # Expect: log_delta("test_domain.b", 2, None)
    pop_calls = mock_tx.log_delta.call_args_list
    assert len(pop_calls) > 0, "No log for pop"
    args = pop_calls[0].args
    assert args[0] == "test_domain.b"
    assert args[1] == 2
    assert args[2] is None
    print(f"[PASS] Logged Pop: {args}")

    # 3. Test Read-Only Enforcement
    print("\n3. Testing Read-Only Enforcement")
    # Create Read-Only Proxy
    ro_proxy = SupervisorProxy(target, "ro_domain", True, None)

    with pytest.raises(PermissionError):
        ro_proxy.pop("a")
    print("[PASS] Read-Only Proxy blocked .pop()")

    with pytest.raises(PermissionError):
        ro_proxy.update({"z": 99})
    print("[PASS] Read-Only Proxy blocked .update()")

    with pytest.raises(PermissionError):
        ro_proxy.clear()
    print("[PASS] Read-Only Proxy blocked .clear()")

    with pytest.raises(PermissionError):
        ro_proxy.setdefault("new", 1)
    print("[PASS] Read-Only Proxy blocked .setdefault()")
