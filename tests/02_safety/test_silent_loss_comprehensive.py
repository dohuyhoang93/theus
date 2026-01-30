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
    print("  [Case 1] Edge Cases (Pop, Remove, Clear) via Engine Process...")
    t.register(proc_edge_cases)
    await t.execute("proc_edge_cases")

    state_1 = t.state.data["domain"]
    assert state_1["items"] == ["final"], f"List edge case failed: {state_1['items']}"
    assert state_1["tags"] == {"omega"}, f"Set edge case failed: {state_1['tags']}"
    val = state_1["meta"]["nested"]["count"]
    assert val == 2, (
        f"State SHOULD match committed transaction (2), but got {val}"
    )
    print("    -> Passed (Lists Leaked, Dicts Protected)")

    # CASE 2: Conflict (Explicit Log vs Implicit Mutation)
    # Theory: Explicit logs are processed. infer_shadow_deltas appends implicit ones.
    # If explicit log touches same path, implicit might overwrite or conflict.
    # We want to see who wins.
    print("  [Case 2] Conflict: Explicit Log vs Implicit Mutation...")
    with t.transaction() as tx:
        from theus_core import SupervisorProxy
        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

        # 1. Implicit Mutation
        root["domain"]["items"].append("implicit")  # items = ["final", "implicit"]

        # 2. Explicit Log (Simulating a specific process override)
        # We manually log a delta saying items = ["explicit"]
        tx.log_delta("domain.items", None, ["explicit"])

        # If infer runs AFTER explicit logs allowment, it might generate a delta based on shadow state.
        # Shadow state has ["final", "implicit"].
        # Original state has ["final"].
        # Delta: SET ["final", "implicit"].
        # Order in delta_log: [SET "explicit"], [SET "final", "implicit"]
        # Last one wins?

    state_2 = t.state.data["domain"]
    print(f"    -> Result: {state_2['items']}")
    # Note: This behavior defines the "Consistency Policy".
    # Usually, we prefer latest action. Implicit mutation happened *during* block.
    # Explicit log happened *during* block.
    # If infer happens at __exit__, it is effectively the "latest" reflection of the object state.

    # CASE 3: Deep Nesting & Object replacement
    print("  [Case 3] Deep Nesting & Replacement...")
    with t.transaction() as tx:
        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

        # Replace entire list object
        root["domain"]["items"] = ["replaced_list"]

        # Verify proxy tracks NEW object?
        # root['domain']['items'] now returns the new list (wrapped in Proxy if accessed again)
        # Assuming we access it again:
        root["domain"]["items"].append("after_replace")

    state_3 = t.state.data["domain"]
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
