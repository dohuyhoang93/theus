import sys
import os
import pytest
from theus import TheusEngine as Theus
from pydantic import BaseModel, Field
from typing import List, Set, Dict


# Define Schema
class Domain(BaseModel):
    items: List[str] = Field(default_factory=list)
    tags: Set[str] = Field(default_factory=set)
    meta: Dict[str, str] = Field(default_factory=dict)


class StateModel(BaseModel):
    domain: Domain


def test_silent_loss_fix():
    print("\n[Test] Verifying Silent Loss Fix (Differential Shadow Merging)...")

    # 1. Setup Engine
    t = Theus()
    t.set_schema(StateModel)

    # 2. Initial State
    initial_data = {
        "domain": {"items": ["initial"], "tags": {"alpha"}, "meta": {"key": "val"}}
    }
    # Use CAS to update engine state (State is immutable)
    t.compare_and_swap(0, data=initial_data)

    # 3. Transaction with In-Place Mutations
    print("[Action] Performing in-place mutations (append, add)...")
    from theus_core import SupervisorProxy

    with t.transaction() as tx:
        # Create Proxy manually (simulating what ContextGuard does)
        # Wrap the root state data
        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

        # Access domain. Items should be lists/sets.
        # Note: t.state.data is likely a FrozenDict/Dict.
        # We access via keys.
        domain = root["domain"]

        # List Mutation (The "Silent Loss" culprit)
        # domain['items'] returns a Proxy wrapping the list
        domain["items"].append("new_item")

        # Set Mutation
        domain["tags"].add("beta")

        # Dict Mutation
        domain["meta"]["new_key"] = "new_val"

        print(f"  > Inside TX: items={domain['items']}, tags={domain['tags']}")

    # 4. Verify Persistence
    final_state = t.state.data
    print(
        f"[Result] Final State: items={final_state['domain']['items']}, tags={final_state['domain']['tags']}"
    )

    assert "new_item" in final_state["domain"]["items"], (
        "List mutation (.append) was LOST!"
    )
    assert "beta" in final_state["domain"]["tags"], "Set mutation (.add) was LOST!"
    assert final_state["domain"]["meta"]["new_key"] == "new_val", (
        "Dict mutation was lost!"
    )

    print("[Success] All mutations persisted correctly!")


if __name__ == "__main__":
    try:
        test_silent_loss_fix()
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
