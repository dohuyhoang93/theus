import pytest
from theus import TheusEngine
from theus.contracts import process

# State is likely available via engine.state, no need to import class explicitly unless for typing


@pytest.fixture
def engine():
    import theus

    print(f"DEBUG: theus path: {theus.__file__}")
    try:
        import theus_core

        print(f"DEBUG: theus_core path: {theus_core.__file__}")
    except ImportError:
        print("DEBUG: theus_core not importable normally.")

    return TheusEngine(strict_guards=False)


def test_silent_overwrite_repro(engine):
    """
    Demonstrates that current 'update' logic is a Deep Replacement, not Deep Merge.
    Sibling fields (domain.user.name) should be preserved when updating (domain.user.age),
    but are currently lost if the update payload is just {domain: {user: {age: ...}}}.
    """
    # 1. Setup Initial State
    initial_data = {
        "domain": {
            "user": {"name": "Alice", "role": "admin", "stats": {"login_count": 5}},
            "meta": {"version": 1},
        }
    }

    # Manually inject state (simulating previous transactions)
    # We use public API for setup
    with engine.transaction() as t:
        t.update(initial_data)

    print("\n[+] Initial State Set:")
    print(engine.state.domain)
    # Re-fetch state just in case reference changed (it shouldn't for domain proxy behavior but...)
    # The assertions assume 'engine.state' is fresh.

    assert engine.state.domain.user.name == "Alice"
    assert engine.state.domain.user.stats.login_count == 5

    # 2. Perform Partial Update
    # Goal: Update only 'login_count' to 6
    update_payload = {"domain": {"user": {"stats": {"login_count": 6}}}}

    print(f"\n[+] Applying Partial Update: {update_payload}")

    with engine.transaction() as t2:
        t2.update(update_payload)

    new_state = engine.state
    print("\n[+] State After Update:")
    print(new_state.domain)

    # 3. Verify Integrity (Expectations)
    assert new_state.domain.user.stats.login_count == 6, "Target field was not updated"

    # 4. Test In-Transaction Overwrite (The Real Bug?)
    print("\n[+] Testing In-Transaction Overwrite...")
    with engine.transaction() as t3:
        # First update
        t3.update({"domain": {"user": {"extra": "field1"}}})
        # Second update - should MERGE, not overwrite "domain" key in pending_data
        t3.update({"domain": {"user": {"other": "field2"}}})

    print(engine.state.domain.user)

    try:
        assert engine.state.domain.user.extra == "field1"
        assert engine.state.domain.user.other == "field2"
        # And original fields preserved
        assert engine.state.domain.user.name == "Alice"
        print("✅ SUCCESS: In-Transaction Deep Merge worked")
    except AttributeError as e:
        print(f"❌ FAILURE: In-Transaction Overwrite Detected! {e}")
        pytest.fail(f"Silent Overwrite within Transaction: {e}")

    # Sibling fields ("name", "role") SHOULD still exist (Deep Merge)
    # BUT currently they will likely be missing (Deep Replacement)
    try:
        assert new_state.domain.user.name == "Alice", "Sibling field 'name' was lost!"
        assert new_state.domain.user.role == "admin", "Sibling field 'role' was lost!"
        assert new_state.domain.meta.version == 1, "Sibling root 'meta' was lost!"
        print("\n✅ SUCCESS: Deep Merge worked (Unexpectedly?)")
    except (AttributeError, KeyError, AssertionError) as e:
        print(f"\n❌ FAILURE CONFIRMED: Data Loss Detected! {e}")
        # We expect this to fail currently, proving the bug.
        pytest.fail(f"Silent Overwrite Bug Confirmed: {e}")


if __name__ == "__main__":
    # verification run
    import sys
    import os
    import importlib

    # Force print buffering off
    sys.stdout.reconfigure(line_buffering=True)

    import theus

    print(f"DEBUG: theus path: {theus.__file__}")
    try:
        import theus_core

        print(f"DEBUG: theus_core path: {theus_core.__file__}")
        print(f"DEBUG: theus_core Size: {os.path.getsize(theus_core.__file__)} bytes")
    except ImportError as e:
        print(f"DEBUG: theus_core import error: {e}")

    try:
        test_silent_overwrite_repro(TheusEngine(strict_guards=False))
    except Exception as e:
        print(e)
