from pop import process
from src.context import SystemContext

@process(
    inputs=['domain.counter', 'domain.data'],
    outputs=['domain.data', 'domain.counter']
)
def hello_world(ctx: SystemContext):
    """
    A simple example process.
    """
    # Valid Read
    current_val = ctx.domain_ctx.counter
    
    # Mutation (Allowed because specified in outputs)
    ctx.domain_ctx.counter += 1
    ctx.domain_ctx.data.append(f"Hello World #{ctx.domain_ctx.counter}")
    
    print(f"[Process] Hello World! Counter is now {ctx.domain_ctx.counter}")
    return "OK"
