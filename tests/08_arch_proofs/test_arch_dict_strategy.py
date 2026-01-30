import pytest
from theus.engine import TheusEngine as Theus
from pydantic import BaseModel, Field
from typing import Dict, Any


# Define Schema
class StateModel(BaseModel):
    tree: Dict[str, Any] = Field(default_factory=dict)


def test_arch_dict_eager_copy_strategy():
    """
    Architectural Proof: Eager Deep Copy for Dicts
    Proves that accessing a Dict Proxy triggers an immediate Deep Copy of the subtree.
    This validates the logic that Dict Proxy acts as the 'Isolation Boundary'.
    """
    print("\n[Proof] Investigating Lazy vs Eager Copy in Dict Tree...")

    t = Theus()
    t.set_schema(StateModel)

    # 1. Setup Deep Tree (Root -> Branch -> Leaf)
    initial_data = {
        "tree": {
            "branch_A": {"leaf_1": "data_1"},
            "branch_B": {  # untouched branch
                "leaf_2": "data_2"
            },
        }
    }
    t.compare_and_swap(0, data=initial_data)

    # Capture Original IDs
    raw_root = t.state.data["tree"]
    raw_branch_b = raw_root["branch_B"]
    original_id_b = id(raw_branch_b)

    print(f"Original Branch B ID: {original_id_b}")

    with t.transaction() as tx:
        from theus_core import SupervisorProxy

        root_proxy = SupervisorProxy(
            t.state.data, path="", read_only=False, transaction=tx
        )

        # 2. Touch the Root (tree)
        # This access should trigger the copy logic.
        print("[Action] Accessed 'tree' (Root)")
        tree_proxy = root_proxy["tree"]

        # 3. Inspect the internals of the Proxy
        # We peek at the 'supervisor_target' (the Shadow Dict)
        shadow_dict = tree_proxy.supervisor_target
        shadow_branch_b = shadow_dict["branch_B"]
        shadow_id_b = id(shadow_branch_b)

        print(f"Shadow Branch B ID : {shadow_id_b}")

        # PROOF: Eager Deep Copy
        # Even though we never touched branch_B, it should have a new ID
        # because the parent 'tree' was deepcopied.
        if shadow_id_b != original_id_b:
            print(
                "   [EAGER] Branch B has a NEW ID. (Deepcopy occurred at Root access)"
            )
        else:
            print(
                "   [LAZY] Branch B is still pointing to Original Object! (Copy-on-Write not fully triggered)"
            )

        # Theus Architecture v3.1 enforces Safety via Deepcopy
        assert shadow_id_b != original_id_b, (
            "Theus Strategy Violation: Expected Eager Deep Copy for Isolation safety."
        )
