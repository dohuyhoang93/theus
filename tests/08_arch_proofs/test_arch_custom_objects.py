import pytest
from theus.engine import TheusEngine as Theus
from pydantic import BaseModel
from typing import Any


# 1. Custom Standard Class (Has __dict__)
class User:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"User({self.name})"


# 2. Custom "Closed" Class (Slots - No __dict__)
class Point:
    __slots__ = ["x", "y"]

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


# Schema
class StateModel(BaseModel):
    user: Any
    point: Any


def test_arch_custom_object_strategies():
    """
    Architectural Proof: Custom Object Handling Strategies
    1. Standard Objects (w/ __dict__) -> Proxied (Active Interception)
    2. Slotted Objects (w/o __dict__) -> Raw Shadow (Passive Inference)
    Both must persist correctly.
    """
    print("\n[Proof] Verifying Custom Object Handling...")

    t = Theus()
    t.set_schema(StateModel)

    # Setup
    initial_data = {"user": User("Alice"), "point": Point(10, 20)}
    t.compare_and_swap(0, data=initial_data)

    with t.transaction() as tx:
        from theus_core import SupervisorProxy

        root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)

        # 1. Test Standard Object -> Should be Proxy
        u = root["user"]
        u_type = str(type(u))
        print(f"\n[Standard Object] Type: {u_type}")

        assert "SupervisorProxy" in u_type, (
            "Standard Objects should be wrapped in SupervisorProxy"
        )
        u.name = "Bob"  # Mutate

        # 2. Test Slotted Object -> Should be Raw
        p = root["point"]
        p_type = str(type(p))
        print(f"\n[Slotted Object] Type: {p_type}")

        assert "SupervisorProxy" not in p_type, (
            "Slotted Objects should NOT be wrapped (Pure Shadow)"
        )
        p.x = 99  # Mutate Raw Shadow

    # Verify Persistence
    final_user = t.state.data["user"]
    final_point = t.state.data["point"]

    print(f"\nFinal User: {final_user}")
    print(f"Final Point: {final_point}")

    assert final_user.name == "Bob", "Active Interception failed for Standard Object"
    assert final_point.x == 99, "Passive Inference failed for Slotted Object"

    print("[SUCCESS] Both object strategies verified.")
