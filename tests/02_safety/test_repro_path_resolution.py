if __name__ == "__main__":
    import sys
    import os

    # Force print buffering off
    sys.stdout.reconfigure(line_buffering=True)

    import theus
    import pytest
    from theus import TheusEngine

    print(f"DEBUG: theus path: {theus.__file__}")

    engine = TheusEngine(strict_guards=False)

    print("\n[+] Testing Transaction with Dot Notation...")
    with engine.transaction() as tx:
        # Update using dot notation
        tx.update({"domain.nested.value": "success"})

    state = engine.state
    print(f"\n[+] State Data Keys: {state.data.keys()}")

    # Check 1: Is it a literal key?
    keys = list(state.data.keys())
    if "domain.nested.value" in keys:
        print("❌ FAILURE: Key 'domain.nested.value' exists as literal key in state!")

        print(f"Value: {state.data['domain.nested.value']}")

    print(f"DEBUG: state.data Type: {type(state.data)}")

    # Check 2: Is it nested?
    # Workaround for potential Proxy Bug (__contains__ raising KeyError)
    # We saw 'domain' in keys(), so let's try direct access
    try:
        domain = state.data["domain"]
        print(f"✅ Accessed state.data['domain'] successfully: {domain}")
        print(f"DEBUG: domain Type: {type(domain)}")

        # Now check logical correctness
        if isinstance(domain, dict) or hasattr(domain, "keys"):
            # If it's a proxy, string represenation might show content
            if "nested" in str(domain) and "success" in str(domain):
                print("✅ SUCCESS: Domain looks correct (contains nested value).")
            else:
                # Try digging deeper
                try:
                    nested = domain["nested"]  # or .nested?
                    print(f"DEBUG: nested: {nested}")
                    val = nested["value"]
                    assert val == "success"
                    print(
                        "✅ SUCCESS: Verified nested structure domain.nested.value == 'success'"
                    )
                except Exception as e:
                    # Try attribute access
                    try:
                        val = domain.nested.value
                        assert val == "success"
                        print(
                            "✅ SUCCESS: Verified via attribute domain.nested.value == 'success'"
                        )
                    except:
                        print(
                            f"❌ FAILURE: Could not verify nested data. Content: {domain}"
                        )
                        sys.exit(1)

    except KeyError:
        print(
            "❌ FAILURE: 'domain' key missing from state.data (despite appearing in keys?)"
        )
        sys.exit(1)
    except Exception as e:
        print(f"❌ FAILURE: Unexpected error accessing domain: {e}")
        sys.exit(1)

    sys.exit(0)
