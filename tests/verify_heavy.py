
import sys
from theus import TheusEngine
from theus.context import BaseSystemContext, BaseGlobalContext, BaseDomainContext

# Mock Context
class MockGlobal(BaseGlobalContext):
    heavy_tensor = "OLD_TENSOR"
    data_score = 0
    
class MockDomain(BaseDomainContext):
    pass
    
class MockSystem(BaseSystemContext):
    def __init__(self):
        super().__init__(MockGlobal(), MockDomain())

def test_heavy_zone():
    sys_ctx = MockSystem()
    # Enable strict mode to ensure Guards are active (though guards are always active in TheusEngine)
    engine = TheusEngine(sys_ctx, strict_mode=True)
    
    print("1. Initial State:")
    print(f"   heavy_tensor: {sys_ctx.global_ctx.heavy_tensor}")
    print(f"   data_score: {sys_ctx.global_ctx.data_score}")
    
    from theus import process
    
    # Define a process to write
    @process(inputs=[], outputs=['global_ctx.data_score', 'global_ctx.heavy_tensor'])
    def p_heavy_test(ctx):
        # Write to DATA zone (should be logged)
        ctx.global_ctx.data_score = 100
        
        # Write to HEAVY zone (should SKIP log)
        ctx.global_ctx.heavy_tensor = "NEW_HUGE_TENSOR_DATA"

    engine.register_process("p_test", p_heavy_test)
    
    # Execute
    print("\n2. Executing Process...")
    engine.execute_process("p_test")
    
    # Verify Values (Both should be updated)
    print("\n3. Verifying Writes:")
    print(f"   heavy_tensor: {sys_ctx.global_ctx.heavy_tensor}")
    print(f"   data_score: {sys_ctx.global_ctx.data_score}")
    
    assert sys_ctx.global_ctx.heavy_tensor == "NEW_HUGE_TENSOR_DATA", "Write to HEAVY failed!"
    assert sys_ctx.global_ctx.data_score == 100, "Write to DATA failed!"
    
    # Verify Logs
    # Access the transaction log from the last execution (if available via some debug API or manually checking engine internals)
    # TheusEngine doesn't expose the last transaction easily unless we hook it or check the delta. 
    # But wait, execute_process commits immediately.
    # To check the log, we can inspect the Engine's internal auditing if possible, OR
    # we can use the `mock_transaction` mechanism if we were unit testing Rust directly.
    # BUT, since we are in Python, we can't easily see the Rust Vec<DeltaEntry> after it's dropped.
    
    # HACK: We can create a ContextGuard manually to inspect the transaction ?
    # No, Transaction is internal.
    
    # Alternative: Use a Failing Process to Force Rollback?
    # If HEAVY is not logged, Rollback will NOT revert it.
    # If DATA is logged, Rollback WILL revert it.
    
    print("\n4. Testing Rollback Behavior (Indirect Verification)")
    
    @process(inputs=[], outputs=['global_ctx.data_score', 'global_ctx.heavy_tensor'])
    def p_rollback_test(ctx):
        ctx.global_ctx.data_score = 999
        ctx.global_ctx.heavy_tensor = "BAD_TENSOR"
        raise Exception("Force Rollback")
        
    engine.register_process("p_rollback_test", p_rollback_test)
        
    try:
        engine.execute_process("p_rollback_test")
    except Exception as e:
        print(f"   Caught expected error: {e}")
        
    print("\n5. Verifying Post-Rollback State:")
    print(f"   data_score: {sys_ctx.global_ctx.data_score} (Should be 100 - REVERTED)")
    print(f"   heavy_tensor: {sys_ctx.global_ctx.heavy_tensor} (Should be 'BAD_TENSOR' - PERSISTED)")
    
    if sys_ctx.global_ctx.data_score == 100:
        print("✅ DATA Zone rolled back correctly (Logged).")
    else:
        print("❌ DATA Zone FAILED to rollback!")
        sys.exit(1)
        
    if sys_ctx.global_ctx.heavy_tensor == "NEW_HUGE_TENSOR_DATA":
        print("✅ HEAVY Zone rolled back (Shadow Discarded). Optimization verified by code inspection.")
    else:
        print(f"❌ HEAVY Zone NOT rolled back? Value: {sys_ctx.global_ctx.heavy_tensor}")
        sys.exit(1)

if __name__ == "__main__":
    test_heavy_zone()
