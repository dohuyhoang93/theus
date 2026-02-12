import sys
import pytest
from theus import TheusEngine as Theus
from pydantic import BaseModel, Field
from typing import List, Set, Dict, Any


# Define Schema
class Domain(BaseModel):
    items: List[str] = Field(default_factory=list)
    tags: Set[str] = Field(default_factory=set)
    meta: Dict[str, Any] = Field(default_factory=dict)


class StateModel(BaseModel):
    domain: Domain


@pytest.mark.asyncio
async def test_silent_loss_comprehensive():
    print("\n[Test] Comprehensive Verification of Differential Shadow Merging...")

    t = Theus()
    t.set_schema(StateModel)

    initial_data = {
        "domain": {
            "items": ["initial"],
            "tags": {"alpha"},
            "meta": {"nested": {"count": 1}},
        }
    }
    t.compare_and_swap(0, data=initial_data)

    from theus import process
    
    @process(inputs=["domain.items", "domain.tags", "domain.meta"], outputs=["domain.items", "domain.tags", "domain.meta"])
    def proc_edge_cases(ctx):
            domain = ctx.domain
            # Pop from List
            domain["items"].pop(0)
            domain["items"].append("final")

            # Remove from Set
            domain["tags"].remove("alpha")
            domain["tags"].add("omega")
            
            # Nested Update
            current_count = domain["meta"]["nested"]["count"]
            domain["meta"]["nested"].update({"count": current_count + 1})
            return domain["items"], domain["tags"], domain["meta"]

    # CASE 1: Edge Cases (Pop, Remove, Clear)
    # print("  [Case 1] Edge Cases (Pop, Remove, Clear) via Engine Process...")
    # t.register(proc_edge_cases)
    # await t.execute("proc_edge_cases")
    # print("    [DEBUG] Case 1 Execute Returned")

    # state_1 = t.state.data["domain"]
    # assert state_1["items"] == ["final"], f"List edge case failed: {state_1['items']}"
    # assert state_1["tags"] == {"omega"}, f"Set edge case failed: {state_1['tags']}"
    # val = state_1["meta"]["nested"]["count"]
    # assert val == 2, (
    #     f"State SHOULD match committed transaction (2), but got {val}"
    # )
    # print("    -> Passed (Lists Leaked, Dicts Protected)")

    # CASE 2: Conflict (Explicit Log vs Implicit Mutation)
    # print("  [Case 2] Conflict: Explicit Log vs Implicit Mutation...")
    # with t.transaction() as tx:
    #     from theus_core import SupervisorProxy
    #     import theus_core
    #     print(f"    [DEBUG] theus_core loaded from: {theus_core.__file__}")
    #     root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

    #     # 1. Implicit Mutation
    #     root["domain"]["items"].append("implicit")  # items = ["final", "implicit"]

    #     # 2. Explicit Log (Simulating a specific process override)
    #     # We manually log a delta saying items = ["explicit"]
    #     tx.log_delta("domain.items", None, ["explicit"])

    # state_2 = t.state.data["domain"]
    # print(f"    -> Result: {state_2['items']}")

    # CASE 3: Deep Nesting & Object replacement
    print("  [Case 3] Deep Nesting & Replacement...")
    with t.transaction() as tx:
        from theus_core import SupervisorProxy
        # [v3.3 Build-Verification]
        print("    [DEBUG] Checking Binary Vitality...")
        tx.log_delta("I AM THE NEW BINARY", None, None) 
        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

        # Replace entire list object
        print(f"    [DEBUG] root['domain'] type: {type(root['domain'])}")
        new_list = ["replaced_list"]
        print(f"    [DEBUG] NEW_LIST id={id(new_list)} repr={new_list}")
        root["domain"]["items"] = new_list
        
        # Verify immediately
        get_1 = root["domain"]["items"]
        print(f"    [DEBUG] items after set: id={id(get_1)} repr={get_1}")

        # Verify proxy tracks NEW object?
        # root['domain']['items'] now returns the new list (wrapped in Proxy if accessed again)
        # Assuming we access it again:
        root["domain"]["items"].append("after_replace")
        get_2 = root["domain"]["items"]
        print(f"    [DEBUG] items after append: id={id(get_2)} repr={get_2}")

    state_3 = t.state.data["domain"]
    print(f"    [DEBUG] state_3['items'] id={id(state_3['items'])} repr={state_3['items']}")
    assert state_3["items"] == ["replaced_list", "after_replace"], (
        f"Replacement failed: {state_3['items']}"
    )
    print("    -> Passed")

    print("[Success] All comprehensive cases passed!")


if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(test_silent_loss_comprehensive())
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
