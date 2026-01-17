
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
    items = ctx.domain_ctx.items
    print("Success!")
    return "ok"

if __name__ == "__main__":
    sys_ctx = MySystem()
    engine = TheusEngine(sys_ctx, strict_mode=True)
    engine.register(my_process)
    
    try:
        engine.execute("my_process")
    except Exception as e:
        print(f"Caught expected error: {type(e).__name__}: {e}")
