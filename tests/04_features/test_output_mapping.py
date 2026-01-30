import pytest
import asyncio
from theus.engine import TheusEngine
from theus import process


# 1. Single Output Mapping
@process(outputs=["domain.status"])
def proc_single(ctx):
    return "Online"


# 2. Multi-Output Mapping (Dict Exact Match)
@process(outputs=["domain.user.name", "domain.user.age"])
def proc_multi_dict(ctx):
    return {"domain.user.name": "Alice", "domain.user.age": 30}


# 3. Multi-Output Mapping (Dict Leaf Match)
@process(outputs=["domain.config.theme", "domain.config.debug"])
def proc_multi_leaf(ctx):
    # Mapping based on leaf names 'theme' and 'debug'
    return {"theme": "Dark", "debug": True}


# 4. Multi-Output Mapping (Positional Tuple)
@process(outputs=["domain.pos.x", "domain.pos.y"])
def proc_multi_tuple(ctx):
    return (100, 200)


@pytest.mark.asyncio
async def test_output_mapping_logic():
    print("\n=== THEUS OUTPUT MAPPING VERIFICATION ===\n")

    eng = TheusEngine(context={})

    # Test 1: Single
    eng.register(proc_single)
    await eng.execute("proc_single")
    assert eng.state.data["domain"]["status"] == "Online"
    print("✅ Single Output Mapping: PASSED")

    # Test 2: Dict Exact
    eng.register(proc_multi_dict)
    await eng.execute("proc_multi_dict")
    assert eng.state.data["domain"]["user"]["name"] == "Alice"
    assert eng.state.data["domain"]["user"]["age"] == 30
    print("✅ Multi-Output (Exact Match): PASSED")

    # Test 3: Dict Leaf
    eng.register(proc_multi_leaf)
    await eng.execute("proc_multi_leaf")
    assert eng.state.data["domain"]["config"]["theme"] == "Dark"
    assert eng.state.data["domain"]["config"]["debug"] is True
    print("✅ Multi-Output (Leaf Match): PASSED")

    # Test 4: Tuple
    eng.register(proc_multi_tuple)
    await eng.execute("proc_multi_tuple")
    assert eng.state.data["domain"]["pos"]["x"] == 100
    assert eng.state.data["domain"]["pos"]["y"] == 200
    print("✅ Multi-Output (Positional Tuple): PASSED")


if __name__ == "__main__":
    asyncio.run(test_output_mapping_logic())
