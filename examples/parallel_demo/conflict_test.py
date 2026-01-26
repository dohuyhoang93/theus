
import asyncio
import os
import sys
import numpy as np
import subprocess
from multiprocessing import shared_memory

# Config
os.environ["THEUS_USE_PROCESSES"] = "1"
sys.path.append(os.path.dirname(__file__))

from theus import TheusEngine
from tasks import saboteur_task

async def test_idempotency_and_sabotage():
    print("\n=== Test 1: Idempotency & Access Control ===")
    engine = TheusEngine()
    
    # 1. Idempotency Check
    print("[*] Allocating 'test_mem'...")
    arr1 = engine.heavy.alloc("test_mem", shape=(1024,), dtype=np.float32)
    arr1[0] = 1337.0
    
    print("[*] Re-allocating 'test_mem' (Should return same buffer)...")
    arr2 = engine.heavy.alloc("test_mem", shape=(1024,), dtype=np.float32)
    
    if arr2[0] == 1337.0:
        print("[+] PASS: Idempotency confirmed. Data persist across calls.")
    else:
        print("[-] FAIL: New buffer created or data lost.")
        
    engine.compare_and_swap(engine.state.version, heavy={'source_data': arr1})
    
    # 2. Sabotage Check
    print("[*] Launching Saboteur Task...")
    engine.register(saboteur_task)
    result = await engine.execute(saboteur_task)
    
    print(f"[Result] {result}")
    
    if result['status'] == 'BLOCKED':
         print("[+] PASS: Unlink blocked by SafeSharedMemory.")
    elif result['status'] == 'DESTROYED':
         print("[-] FAIL: Worker successfully destroyed memory!")
    else:
         print(f"[-] FAIL: Unexpected status {result['status']}")

async def test_namespace_stress():
    print("\n=== Test 2: Namespace Stress (Multi-Process) ===")
    print("[*] Launching 2 instances of main.py interactively...")
    
    # Path to main.py
    main_script = os.path.join(os.path.dirname(__file__), "main.py")
    
    # Launch 2 processes
    p1 = subprocess.Popen([sys.executable, main_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen([sys.executable, main_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print("[*] Waiting for completion...")
    out1, err1 = p1.communicate()
    out2, err2 = p2.communicate()
    
    if p1.returncode == 0 and p2.returncode == 0:
        print("[+] PASS: Both processes finished successfully.")
        # Check basic output
        if b"MATCH" in out1 and b"MATCH" in out2:
             print("[+] PASS: Both verified calculation correctness.")
        else:
             print("[-] WARNING: Correctness verification output missing.")
    else:
        print(f"[-] FAIL: Crash detected. Return Codes: {p1.returncode}, {p2.returncode}")
        print("STDERR 1:", err1.decode())
        print("STDERR 2:", err2.decode())

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_idempotency_and_sabotage())
    
    # Run synchronous stress test
    loop.run_until_complete(test_namespace_stress())
