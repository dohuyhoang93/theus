import pytest
import asyncio
from theus.engine import TheusEngine
from theus import process
from theus.contracts import SemanticType


# ==========================================
# 1. Functional Pattern (Copy-Mutate-Return)
# ==========================================
@process(inputs=["domain.data"], outputs=["domain.data"])
def functional_process(ctx):
    # Functional style: Copy, Mutate Local, Return
    current = ctx.domain.data
    # In functional style, we treat input as immutable source
    new_data = current.copy() if hasattr(current, "copy") else dict(current)
    new_data["functional"] = "Success"
    return new_data


# ==========================================
# 2. Idiomatic Zero Trust (Direct Mutation)
# ==========================================
@process(inputs=["domain.data"], outputs=["domain.data"])
def idiomatic_process(ctx):
    # Idiomatic style: Mutate Proxy directly
    # This relies on Zero Trust mutators (hijacked __setitem__, update, pop)
    ctx.domain.data["idiomatic"] = "Success"
    ctx.domain.data.update({"idiomatic_update": "Success"})
    # Return None so Engine doesn't overwrite 'domain.data' with a string
    return None


@process(inputs=["domain.data"], outputs=["domain.data"])
def idiomatic_failure_rollback(ctx):
    # Mutate then Fail
    ctx.domain.data["rollback_target"] = "FailedState"
    raise RuntimeError("Simulated Crash")


@process(inputs=["domain.data"], semantic=SemanticType.PURE)
def idiomatic_audit_violation(ctx):
    # ReadOnly Violation
    ctx.domain.data["illegal"] = "ShouldNotHappen"


# ==========================================
# 3. Explicit API (Transaction)
# ==========================================
@process(inputs=["domain.data", "transaction"], outputs=["transaction"])
def explicit_process(ctx):
    # Explicit Transaction API
    # Note: Deep merge behavior applies
    ctx.transaction.update(data={"domain": {"data": {"explicit": "Success"}}})
    return None


@process(inputs=["domain.data", "transaction"], outputs=["transaction"])
def explicit_failure_rollback(ctx):
    ctx.transaction.update(
        data={"domain": {"data": {"rollback_target": "FailedState"}}}
    )
    raise RuntimeError("Simulated Crash")


@pytest.mark.asyncio
async def test_universal_mutation_patterns():
    print("\n=== THEUS UNIVERSAL STATE MUTATION TEST ===\n")

    # Init Engine
    initial_state = {"domain": {"data": {"original": "Preserved"}}}
    eng = TheusEngine(context=initial_state)

    # State.data is a PyDict in Rust, exposed to Python
    print(f"Initial State: {eng.state.data}")

    # ------------------------------------------------
    # TEST 1: Functional Pattern (Copy-Mutate-Return)
    # ------------------------------------------------
    print("\n[TEST 1] Functional Pattern (Return Output)")

    # Note: eng.execute() is synchronous wrapper that handles async loop if needed
    eng.register(functional_process)
    await eng.execute("functional_process")

    state = eng.state.data
    print(f"DEBUG STATE: {state}")
    assert state["domain"]["data"]["functional"] == "Success", (
        "Functional update failed"
    )
    assert state["domain"]["data"]["original"] == "Preserved", (
        "Silent overwrite logic failed"
    )
    print("✅ Functional Pattern: PASSED")

    # ------------------------------------------------
    # TEST 2: Idiomatic Zero Trust (Direct Mutation)
    # ------------------------------------------------
    print("\n[TEST 2] Idiomatic Zero Trust (Proxy Mutation)")
    eng.register(idiomatic_process)
    await eng.execute("idiomatic_process")

    state = eng.state.data
    assert state["domain"]["data"]["idiomatic"] == "Success", "__setitem__ failed"
    assert state["domain"]["data"]["idiomatic_update"] == "Success", ".update() failed"
    print("✅ Idiomatic Pattern: PASSED")

    # ------------------------------------------------
    # TEST 3: Explicit API (Transaction)
    # ------------------------------------------------
    print("\n[TEST 3] Explicit API (Transaction.update)")
    # Reset
    eng = TheusEngine(context={"domain": {"data": {"original": "Preserved"}}})
    eng.register(explicit_process)
    await eng.execute("explicit_process")

    state = eng.state.data
    assert state["domain"]["data"]["explicit"] == "Success", "Explicit update failed"
    assert state["domain"]["data"]["original"] == "Preserved", "Deep Merge failed"
    print("✅ Explicit API: PASSED")

    # ------------------------------------------------
    # TEST 4: Audit Violation (Read Only)
    # ------------------------------------------------
    print("\n[TEST 4] Audit Violation (Read Only Enforcement)")
    try:
        eng.register(idiomatic_audit_violation)
        await eng.execute("idiomatic_audit_violation")
        pytest.fail("ReadOnly process successfully mutated state!")
    except Exception as e:
        # PURE contracts force RO
        assert (
            "read-only" in str(e).lower()
            or "pure" in str(e).lower()
            or "permission" in str(e).lower()
        )
        print(f"✅ Audit Violation: PASSED (Blocked with error: {e})")

    # ------------------------------------------------
    # TEST 5: Idiomatic Rollback (Mutation -> Crash)
    # ------------------------------------------------
    print("\n[TEST 5] Idiomatic Rollback (Mutation then Crash)")
    eng.state.data["domain"]["data"]["rollback_target"] = "Safe"
    try:
        eng.register(idiomatic_failure_rollback)
        await eng.execute("idiomatic_failure_rollback")
    except RuntimeError:
        print("   (Crash caught as expected)")

    state = eng.state.data
    assert state["domain"]["data"]["rollback_target"] == "Safe", (
        f"Rollback failed: {state['domain']['data']['rollback_target']}"
    )
    print("✅ Idiomatic Rollback: PASSED")

    # ------------------------------------------------
    # TEST 6: Explicit Rollback (Tx Update -> Crash)
    # ------------------------------------------------
    print("\n[TEST 6] Explicit Rollback (Tx Update then Crash)")
    eng.state.data["domain"]["data"]["rollback_target"] = "Safe"
    try:
        eng.register(explicit_failure_rollback)
        await eng.execute("explicit_failure_rollback")
    except RuntimeError:
        print("   (Crash caught as expected)")

    state = eng.state.data
    assert state["domain"]["data"]["rollback_target"] == "Safe", (
        f"Rollback failed: {state['domain']['data']['rollback_target']}"
    )
    print("✅ Explicit Rollback: PASSED")
