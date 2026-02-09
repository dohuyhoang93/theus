import pytest
import asyncio
from theus.engine import TheusEngine
from theus.contracts import ProcessContract, SemanticType

@pytest.mark.asyncio
async def test_flyweight_guards():
    engine = TheusEngine()
    
    policy_ids = []
    
    async def proc_1(ctx):
        policy_ids.append(ctx.policy_id)
        return "ok"
    
    async def proc_2(ctx):
        policy_ids.append(ctx.policy_id)
        return "ok"
    
    # Configure with identical inputs/outputs
    contract = ProcessContract(
        inputs=["domain.foo"], 
        outputs=["domain.bar"],
        semantic=SemanticType.EFFECT
    )
    
    # Manually attach contract (since we aren't using @process decorator)
    proc_1._pop_contract = contract
    proc_2._pop_contract = contract
    
    await engine.execute(proc_1)
    await engine.execute(proc_2)
    
    print(f"Policy ID 1: {policy_ids[0]}")
    print(f"Policy ID 2: {policy_ids[1]}")
    
    assert policy_ids[0] == policy_ids[1], "Flyweight failed: Different policy instances for identical config!"
    print("SUCCESS: Flyweight Pattern Verified (Shared Policy Instance)")

    # Test different config
    different_contract = ProcessContract(
        inputs=["domain.other"], 
        outputs=[],
        semantic=SemanticType.EFFECT
    )
    proc_2._pop_contract = different_contract
    
    await engine.execute(proc_2)
    
    print(f"Policy ID 3 (Different): {policy_ids[2]}")
    assert policy_ids[2] != policy_ids[0], "Flyweight Error: Same policy for different config!"
    print("SUCCESS: Flyweight Discrimination Verified")

if __name__ == "__main__":
    asyncio.run(test_flyweight_guards())
