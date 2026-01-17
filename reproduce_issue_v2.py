
import asyncio
from dataclasses import dataclass, field
from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

@dataclass
class MyDomain(BaseDomainContext):
    items: list = field(default_factory=list)

@dataclass
class MyGlobal(BaseGlobalContext):
    pass

@dataclass
class MySystem(BaseSystemContext):
    domain_ctx: MyDomain = field(default_factory=MyDomain)
    global_ctx: MyGlobal = field(default_factory=MyGlobal)

@process(inputs=['domain_ctx.items'], outputs=['domain_ctx.items'])
def my_process(ctx):
    # This should fail if ctx (RestrictedStateProxy) doesn't have domain_ctx
    print("Accessing domain_ctx...")
    try:
        items = ctx.domain_ctx.items
        print("Success!")
    except AttributeError:
        print("Failed logic: ctx.domain_ctx does not exist.")
        # Try fallback
        try:
             print("Trying ctx.domain...")
             items = ctx.domain.items
             print("Success with ctx.domain!")
        except Exception as e:
             print(f"Failed ctx.domain too: {e}")
             
    return "ok"

async def main():
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_mode=True)
    engine.register(my_process)
    
    print("Executing...")
    try:
        await engine.execute("my_process")
    except Exception as e:
        print(f"Caught execution error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
