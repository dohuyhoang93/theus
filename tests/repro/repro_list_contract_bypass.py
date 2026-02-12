from theus import TheusEngine, process
import asyncio

# 1. Setup engine with a list
data = {"domain": {"my_list": [1], "my_dict": {"a": 1}}}
engine = TheusEngine(context=data)

# 2. Define a process that declares my_list as INPUT but NOT OUTPUT
@process(inputs=["domain.my_list"], outputs=[])
def illegal_mutation_process(ctx):
    print(f"   [Process] ctx.domain.my_list = {ctx.domain.my_list}")
    
    # Mutation 1: DICT (Should be blocked by SupervisorProxy)
    print("   [Process] Attempting Dict mutation (Illegal)...")
    try:
        ctx.domain.my_dict['b'] = 2 
    except Exception as e:
        print(f"   [Process] ✅ Dict mutation BLOCKED as expected: {e}")

    # Mutation 2: LIST (Passive Inference Backdoor?)
    print("   [Process] Attempting List mutation (Illegal - Not in outputs)...")
    ctx.domain.my_list.append(2)
    print(f"   [Process] List mutated in-memory: {ctx.domain.my_list}")

async def run_test():
    print("--- TEST: CONTRACT BYPASS (LIST) ---")
    print(f"Initial State: {engine.state.domain['my_list']}")
    
    await engine.execute(illegal_mutation_process)
    
    final_list = engine.state.domain['my_list']
    print(f"Final State:   {final_list}")
    
    if len(final_list) > 1:
        print("❌ CRITICAL: Unauthorized list mutation was PERSISTED!")
    else:
        print("✅ SUCCESS: Unauthorized list mutation was DISCARDED.")

if __name__ == "__main__":
    asyncio.run(run_test())
