from dataclasses import dataclass
import sys
import os

# Add parent directory to path to simulate package installation
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pop import BaseGlobalContext, BaseDomainContext, BaseSystemContext, POPEngine, process

# 1. Define Context
@dataclass
class MyGlobal(BaseGlobalContext):
    counter: int = 0

@dataclass
class MyDomain(BaseDomainContext):
    pass

@dataclass
class MySystem(BaseSystemContext):
    global_ctx: MyGlobal
    domain_ctx: MyDomain

# 2. Define Process
@process(
    inputs=['global.counter'],
    outputs=['global.counter']
)
def increment_counter(ctx):
    print(f"Current Counter: {ctx.global_ctx.counter}")
    ctx.global_ctx.counter += 1
    return "Done"

# 3. Validation Run
if __name__ == "__main__":
    print("--- POP SDK Hello World ---")
    
    # Init
    system = MySystem(MyGlobal(), MyDomain())
    engine = POPEngine(system)
    
    # Register & Run
    engine.register_process("p_inc", increment_counter)
    
    engine.run_process("p_inc")
    engine.run_process("p_inc")
    
    print(f"Final Global Counter: {system.global_ctx.counter}")
    
    if system.global_ctx.counter == 2:
        print("SUCCESS: Pop SDK is working correctly!")
    else:
        print("FAILURE: Counter mismatch.")
