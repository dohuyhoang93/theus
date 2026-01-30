import pytest
from theus import TheusEngine


def test_proxy_containment_leak():
    print("\n--- Testing Proxy Containment (The Naked Object Problem) ---")
    eng = TheusEngine(context={"domain": {"nested": {"secret": "data"}}})
    proxy = eng.state.domain

    # 1. Test .get()
    # Expectation: .get("nested") should return a SupervisorProxy, NOT a dict
    val = proxy.get("nested")
    print(f"Type of proxy.get('nested'): {type(val)}")

    if isinstance(val, dict):
        # Allow if it's FrozenDict (immutable), but Strict Proxy uses SupervisorProxy
        # SupervisorProxy is NOT a dict, it's a Mapping.
        pytest.fail(
            "LEAK DETECTED: .get() returned raw dict! Future mutations won't be tracked."
        )
    else:
        print(f"[PASS] .get() returned wrapped object: {type(val)}")

    # 2. Test .values()
    # Expectation: Iterating values should yield Proxies
    print("\nTesting .values() iteration:")
    values = list(proxy.values())
    first_val = values[0]
    print(f"Type of first value from .values(): {type(first_val)}")
    assert not isinstance(first_val, dict), (
        "LEAK DETECTED: .values() yielded raw dicts."
    )

    # 3. Test .items()
    print("\nTesting .items() iteration:")
    items = list(proxy.items())
    k, v = items[0]
    print(f"Type of value from .items(): {type(v)}")
    assert not isinstance(v, dict), "LEAK DETECTED: .items() yielded raw dicts."

    # 4. Test __len__
    print("\nTesting len(proxy):")
    length = len(proxy)
    assert length == 1
    print(f"[PASS] len(proxy) = {length}")

    # 5. Test Equality
    print("\nTesting Equality:")
    # Note: SupervisorProxy compares against dict by content
    is_eq = proxy == {"nested": {"secret": "data"}}
    assert is_eq, "Proxy logic equality failed"
    print(f"[PASS] proxy == dict: {is_eq}")
