import time
import logging
from theus import process
from src.context import DemoSystemContext

# Simulate Logging
logger = logging.getLogger("ChainProcess")

@process(inputs=['domain.items'], outputs=['domain.items'])
def p_init(ctx):
    """Step 1: Create Data"""
    logger.info(">>> [p_init] START")
    ctx.domain_ctx.items = ["Alpha", "Beta", "Gamma"]
    time.sleep(0.1) # Faster simulation
    logger.info("<<< [p_init] END")
    return "Created"

@process(
    inputs=['domain.status', 'domain.items', 'domain.processed_count'],
    outputs=['domain.status', 'domain.processed_count', 'domain.items']
)
def p_process(ctx: DemoSystemContext):
    print(f"   [p_process] Processing Batch (Current: {ctx.domain_ctx.processed_count})...")
    """Step 2: Heavy Calculation"""
    logger.info(">>> [p_process] START HEAVY WORK")
    count = 0
    for item in ctx.domain_ctx.items:
        # Simulate CPU work per item
        time.sleep(0.1) 
        count += 1
    
    ctx.domain_ctx.processed_count = count
    logger.info(f"<<< [p_process] END (Count={count})")
    return "Processed"

@process(inputs=['domain.status'], outputs=['domain.status'])
def p_finalize(ctx):
    """Step 3: Update Status"""
    logger.info(">>> [p_finalize] START")
    ctx.domain_ctx.status = "SUCCESS"
    logger.info("<<< [p_finalize] END")
    print("\n✅ [WORKFLOW COMPLETE] Press ENTER to continue...") # Visual Cue
    return "Done"
