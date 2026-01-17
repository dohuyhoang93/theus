import sys
import os

# Ensure we can find theus
sys.path.insert(0, os.getcwd())

try:
    from theus.parallel import InterpreterPool
    from standalone_task import standalone_add
    
    print(">> Initializing Pool...")
    pool = InterpreterPool(size=1)
    
    print(">> Submitting Standalone Pure Task...")
    future = pool.submit(standalone_add, 10, 20)
    
    print(">> Waiting for result...")
    result = future.result()
    
    print(f"✅ Success! Result: {result}")
    
    # Check isolation
    import os
    if result['pid'] != os.getpid():
         print(f"✅ PID verified: Main={os.getpid()}, Sub={result['pid']}")
    else:
         # Note: sub-interpreters share PID in some implementations (threads), 
         # but PEP 554 usually implies thread-based isolation in same process.
         # Actually sub-interpreters share the SAME PID because they are in the same process.
         # They have different Interpreter IDs.
         # But the verify_pure.py is just to check if it RUNS.
         print(f"ℹ️ PIDs match (Expected for sub-interpreters): {result['pid']}")

    pool.shutdown()

except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()

