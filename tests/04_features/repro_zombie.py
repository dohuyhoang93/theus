import os
import time
import sys

# Ensure we can import theus
sys.path.insert(0, os.path.abspath("."))
from theus.structures import ManagedAllocator
from multiprocessing import shared_memory
import signal


def create_zombie():
    print(f"[Zombie] PID: {os.getpid()}")

    # 1. Create Allocator (Registers itself)
    alloc = ManagedAllocator(capacity_mb=10)

    # 2. Allocate SHM
    name = "zombie_data"
    print(f"[Zombie] Allocating {name}...")
    try:
        arr = alloc.alloc(name, (1024,), dtype="float64")
        arr[0] = 123.456
        print("[Zombie] Allocated. SHM should be registered.")
    except Exception as e:
        print(f"[Zombie] Allocation failed: {e}")
        return

    # 3. Verify it exists
    # Check registry file
    if os.path.exists(".theus_memory_registry.jsonl"):
        print("[Zombie] Registry file exists.")
        with open(".theus_memory_registry.jsonl", "r") as f:
            print("[Zombie] Registry Content:", f.read().strip())
    else:
        print("[Zombie] ERROR: Registry file NOT created.")

    # 4. Crash hard (os._exit to avoid cleanup)
    print("[Zombie] COMMITING SUICIDE (os._exit). Memory should leak.")
    os._exit(1)


if __name__ == "__main__":
    create_zombie()
