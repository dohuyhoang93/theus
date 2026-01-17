import time
from theus import process
from src.context import DemoSystemContext

# Decorator enforces Contract (Input/Output Safety)

@process(
    inputs=[], 
    outputs=['domain_ctx.status'],
    side_effects=['I/O']
)
def p_init(ctx: DemoSystemContext):
    print("   [p_init] Initializing System Resources...")
    ctx.domain_ctx.status = "READY"
    time.sleep(0.5) # Simulate IO
    return "Initialized"

@process(
    inputs=['domain_ctx.status', 'domain_ctx.items', 'domain_ctx.processed_count'],
    outputs=['domain_ctx.status', 'domain_ctx.processed_count', 'domain_ctx.items'],
    side_effects=['I/O']
)
def p_process(ctx: DemoSystemContext):
    print(f"   [p_process] Processing Batch (Current: {ctx.domain_ctx.processed_count})...")
    
    # Simulate Work
    ctx.domain_ctx.status = "PROCESSING"
    time.sleep(1.0) # Simulate Heavy Compute
    
    # Logic
    ctx.domain_ctx.processed_count += 10
    ctx.domain_ctx.items.append(f"Batch_{ctx.domain_ctx.processed_count}")
    
    return "Processed"

@process(inputs=[], outputs=[])
def save_checkpoint_placeholder(ctx: DemoSystemContext):
    print("   [save_checkpoint] Saving system state...")
    return "Saved"

@process(
    inputs=['domain_ctx.status'], 
    outputs=['domain_ctx.status'],
    side_effects=['I/O']
)
def p_finalize(ctx: DemoSystemContext):
    print("   [p_finalize] Finalizing and Cleaning up...")
    ctx.domain_ctx.status = "SUCCESS"
    time.sleep(0.5)
    print("\n   ✨ [WORKFLOW COMPLETE] Press ENTER to continue...", end="", flush=True) 
    return "Done"
