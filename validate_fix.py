
import asyncio
from dataclasses import dataclass, field
from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext, BaseGlobalContext

try:
    from theus.parallel import INTERPRETERS_SUPPORTED
    print(f"Parallel module imported. Interpreters Supported: {INTERPRETERS_SUPPORTED}")
except ImportError as e:
    print(f"FAILED: parallel module import failed: {e}")
    exit(1)

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

# Contract uses 'domain.items' as per new docs (updated from domain_ctx in 02_CONTRACTS...)
# Code uses 'ctx.domain.items' as per new docs
@process(inputs=['domain.items'], outputs=['domain.items'])
async def my_process(ctx):
    print("Process started.")
    # Access via domain (new doc standard)
    items = ctx.domain.items
    items.append("worked")
    print("Accessed ctx.domain successfully.")
    return "ok"

async def main():
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_mode=True)
    engine.register(my_process)
    
    print("Executing engine.execute...")
    # Async execution (new doc standard)
    result = await engine.execute("my_process")
    print(f"Result: {result}")
    
    if sys_ctx.domain_ctx.items == ["worked"]:
        print("SUCCESS: State updated correctly.")
    else:
        print(f"FAILURE: State not updated: {sys_ctx.domain_ctx.items}")

if __name__ == "__main__":
    asyncio.run(main())
