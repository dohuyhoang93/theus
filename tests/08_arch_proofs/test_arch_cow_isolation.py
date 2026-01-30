import pytest
from theus.engine import TheusEngine as Theus
from pydantic import BaseModel, Field
from typing import List


# Define Schema
class Domain(BaseModel):
    items: List[str] = Field(default_factory=list)


class StateModel(BaseModel):
    domain: Domain


def test_arch_cow_isolation_list():
    """
    Architectural Proof: List Snapshot Isolation
    Proves that Theus returns a detached Shadow Copy for Lists, not the Original.
    Proves that Original remains immutable during transaction.
    """
    print("\n[Proof] Verifying Copy-on-Write (Snapshot Isolation) for Lists...")

    t = Theus()
    t.set_schema(StateModel)

    # 1. Setup Initial State
    initial_items = ["original"]
    t.compare_and_swap(0, data={"domain": {"items": initial_items}})

    # Capture direct reference to internal state BEFORE transaction
    # We navigate carefully to get the raw object from the immutable state container
    raw_state_before = t.state.data
    raw_list_ref = raw_state_before["domain"]["items"]
    original_id = id(raw_list_ref)

    print(f"1. Initial State Address: {original_id} | Content: {raw_list_ref}")

    with t.transaction() as tx:
        from theus_core import SupervisorProxy

        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

        # 2. Access List (Should trigger CoW/Shadowing)
        shadow_list = root["domain"]["items"]
        shadow_id = id(shadow_list)
        print(f"2. Transaction Shadow Address: {shadow_id}")

        # PROOF 1: Identity Check
        # The Shadow MUST be a different object (detached copy)
        assert shadow_id != original_id, (
            "Shadow has SAME ID as Original! (No Isolation?)"
        )
        print("   [OK] Shadow has DIFFERENT ID than Original (Detached Copy).")

        # 3. Mutate Shadow
        print("3. Mutating Shadow (append 'modified')...")
        shadow_list.append("modified")

        # PROOF 2: Integrity of Original Access
        print(f"   Original Content: {raw_list_ref}")
        assert "modified" not in raw_list_ref, (
            "Isolation Failed: Mutation leaked to Original State immediately!"
        )
        print("   [OK] Original Object remains UNTOUCHED.")

    # 4. Verify Final State (Commit)
    final_state = t.state.data["domain"]["items"]
    print(f"4. Final State Content: {final_state}")

    assert "modified" in final_state, "Changes lost after commit!"
    print("   [OK] Commit applied successfully.")
