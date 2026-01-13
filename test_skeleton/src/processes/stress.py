import time
from theus import process
from src.context import DemoSystemContext

@process(
    inputs=[], 
    outputs=['domain_ctx.status'], 
    side_effects=['I/O'],
    errors=['ValueError']
) # Declared correctly
def p_crash_test(ctx: DemoSystemContext):
    print("   [p_crash_test] About to crash...")
    time.sleep(0.5)
    raise ValueError("Simulated Process Crash!")

@process(
    inputs=['domain_ctx.processed_count'], 
    outputs=['domain_ctx.processed_count'],
    side_effects=['I/O'],
    errors=['RuntimeError']
)
def p_transaction_test(ctx: DemoSystemContext):
    print(f"   [p_transaction_test] ORIGINAL VALUE: {ctx.domain_ctx.processed_count}")
    print("   [p_transaction_test] Writing DIRTY DATA (9999)...")
    ctx.domain_ctx.processed_count = 9999
    time.sleep(0.5)
    print("   [p_transaction_test] Simulating CRASH...")
    raise RuntimeError("Transaction Failure!")

# MALICIOUS PROCESS: Attempts to write 'domain.status' 
# BUT does NOT declare it in outputs!
@process(inputs=[], outputs=[]) 
def p_unsafe_write(ctx: DemoSystemContext):
    print("   [p_unsafe_write] Attempting illegal write to 'status'...")
    # This should trigger ContextGuardViolation in Strict Mode
    ctx.domain_ctx.status = "HACKED"
    return "Malicious"
