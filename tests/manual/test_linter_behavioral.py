from theus.contracts import process

# Goal: Verify "Iron Discipline" and Zone Physics Enforcement
# This file intentionally violates multiple semantic rules.

@process(inputs=["domain.log_history"], outputs=["domain.log_history"])
async def task_log_violations(ctx):
    # 1. Assignment Paradox: Direct assignment to a Log Path
    ctx.domain.log_history = ["cheating"] # ERROR: POP-E07
    
    # 2. Mutation Paradox: Destructive method on Log Path
    ctx.domain.log_history.pop() # ERROR: POP-E07
    ctx.domain.log_history.clear() # ERROR: POP-E07
    
    # 3. Valid Log Behavior: Append is the only way
    ctx.domain.log_history.append("valid_event") # OK: Permitted
    ctx.domain.log_history.extend(["e1", "e2"]) # OK: Permitted

@process(inputs=["domain.meta_config"], outputs=["domain.meta_config"])
async def task_meta_violations(ctx):
    # 4. Meta Violation: Any mutation on Read-Only Zone
    ctx.domain.meta_config.update({"k": "v"}) # ERROR: POP-E07
    ctx.domain.meta_config = {"new": "val"} # ERROR: POP-E07

@process(inputs=["domain.data_user"], outputs=["domain.data_user"])
async def task_data_mutations(ctx):
    # 5. Standard Data Violation: Direct mutation (should use CoW return)
    ctx.domain.data_user.append(1) # ERROR: POP-E05 (Should be flagged to encourage CoW)
    ctx.domain.data_user = {"x": 1} # ERROR: POP-E05
    
    # 6. OK: Returning a Delta
    return {"domain.data_user": {"x": 2}}

@process(inputs=["sig_system"], outputs=["sig_system"])
async def task_signal_violations(ctx):
    # 7. Signal Paradox: You can't assign to a signal. Use outbox.
    ctx.sig_system = 1 # ERROR: POP-E07
