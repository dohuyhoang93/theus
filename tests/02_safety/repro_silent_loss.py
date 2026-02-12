import sys
import os
import pytest
from theus import TheusEngine as Theus
try:
    from theus.engine import SupervisorProxy
except ImportError:
    from theus_core import SupervisorProxy

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
    print("\n[Test] Verifying Silent Loss Fix (Address Verification Mode)...")

    # 1. Setup Engine
    t = Theus()
    t.set_schema(StateModel)

    # 2. Initial State
    initial_data = {
        "domain": {"items": ["initial"], "tags": {"alpha"}, "meta": {"key": "val"}}
    }
    t.compare_and_swap(0, data=initial_data)

    # 3. Transaction with In-Place Mutations
    print("[Action] Performing in-place mutations (append, add)...")

    with t.transaction() as tx:
        # Create Proxy manually
        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
        
        # Access domain.
        domain = root["domain"]
        print(f"[DEBUG] Domain Proxy ID: {id(domain)}")

        # [VERIFICATION] Trace Object Identity
        items_proxy = domain["items"]
        print(f"[DEBUG] Items Proxy: {items_proxy} (Type: {type(items_proxy)})")
        print(f"[DEBUG] Items Proxy ID: {id(items_proxy)}")

        # List Mutation
        print(f"[DEBUG] Pre-Append: {items_proxy}")
        items_proxy.append("new_item")
        print(f"[DEBUG] Post-Append: {items_proxy}")
        
        # Verify immediately via fresh access
        items_check = domain["items"]
        print(f"[DEBUG] Check Access ID: {id(items_check)} Content: {items_check}")
        
        if id(items_proxy) != id(items_check):
             print(f"[WARN] Items Proxy ID unstable! {id(items_proxy)} -> {id(items_check)}")
        
        if "new_item" not in items_check:
             print(f"[FATAL] Immediate Check Failed! Appended item lost.")
             print(f"[FATAL] Original ID: {id(items_proxy)} vs Fresh ID: {id(items_check)}")

        # Set Mutation
        domain["tags"].add("beta")
        # Dict Mutation
        domain["meta"]["new_key"] = "new_val"

        print(f"  > Inside TX: items={items_proxy}, tags={domain['tags']}")

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
    test_silent_loss_fix()
