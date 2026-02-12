from theus.engine import TheusEngine
from theus.contracts import process
import asyncio

print("Verifying Transaction Guard Whitelist...")

@process(inputs=["transaction"])
def my_proc(ctx):
    print("Inside process -- accessing transaction...")
    # Access transaction to trigger ContextGuard.__getattr__ -> apply_guard -> get_shadow
    t = ctx.transaction
    print(f"Got transaction object: {t}")
    return "OK"

try:
    engine = TheusEngine()
    engine.register(my_proc)
    
    async def main():
        await engine.execute("my_proc")
        
    asyncio.run(main())
    print("SUCCESS: Transaction accessed safely without DeepCopy error")

except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
