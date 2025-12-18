import logging
import time
from theus import process, ContractViolationError

logger = logging.getLogger("StressTests")

@process(inputs=[], outputs=[])
def p_unsafe_write(ctx):
    """
    Tries to write to Context WITHOUT declaring it in outputs.
    Should Trigger: ContractViolation or LockViolation.
    """
    logger.info(">>> [p_unsafe_write] START: Attempting Illegal Mutation...")
    
    # This is ILLEGAL because 'domain.status' is not in outputs=['...']
    # ContextGuard (Layer 2) should catch this.
    try:
        ctx.domain_ctx.status = "HACKED"
    except Exception as e:
        logger.error(f"🛑 CAUGHT EXPECTED ERROR: {e}")
        return "Blocked"
        
    return "Failed to Block"

def raw_unsafe_function(ctx):
    """
    A raw function (not a process) trying to write.
    Should Trigger: LockViolation (Layer 1 Mutex/Permission).
    """
    logger.info(">>> [raw_unsafe] Attempting raw write...")
    ctx.domain_ctx.status = "RAW_HACKED"

@process(inputs=[], outputs=['domain.status'])
def p_crash_test(ctx): # Assuming DemoSystemContext is not strictly needed for this example, or it's implicitly available.
    print("   [p_crash_test] About to crash...")
    time.sleep(0.5)
    raise ValueError("Simulated Process Crash!")

@process(inputs=['domain.processed_count'], outputs=['domain.processed_count'])
def p_transaction_test(ctx): # Assuming DemoSystemContext is not strictly needed for this example, or it's implicitly available.
    """
    Demonstrates Transaction Rollback.
    1. Sets processed_count to 9999 (Dirty Write).
    2. Crashes.
    3. Engine should Rollback processed_count to original value.
    """
    print(f"   [p_transaction_test] ORIGINAL VALUE: {ctx.domain_ctx.processed_count}")
    print("   [p_transaction_test] Writing DIRTY DATA (9999)...")
    ctx.domain_ctx.processed_count = 9999
    time.sleep(0.5)
    print("   [p_transaction_test] Simulating CRASH...")
    raise RuntimeError("Transaction Failure!")

@process(inputs=['domain.items'], outputs=[])
def p_audit_violation(ctx):
    """
    Simulates input data that violates Business Logic (Audit Recipe).
    Suppose Audit says: items list cannot be empty.
    """
    logger.info(">>> [p_audit_violation] logic...")
    # This logic is fine, but if we feed it bad data, Audit should block ENTRY.
    return "OK"
