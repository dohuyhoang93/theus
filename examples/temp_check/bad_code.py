
from theus import process

@process
def bad_assignment(ctx):
    # This should be caught by POP-E05
    ctx.domain.balance = 1000 
    return {}

@process
def bad_augmentation(ctx):
    # This should be caught by POP-E05
    ctx.domain.counter += 1
    return {}

@process
def bad_method_call(ctx):
    # This is currently NOT caught, but should be?
    ctx.domain.items.append(1)
    return {}
