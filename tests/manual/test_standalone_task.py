def standalone_add(ctx, x, y):
    """
    A purely standalone function with NO dependencies on 'theus'.
    """
    import os
    import threading

    return {
        "result": x + y,
        "pid": os.getpid(),
        "tid": threading.get_ident(),
        "context": "standalone",
    }

if __name__ == "__main__":
    import asyncio
    from theus import TheusEngine

    async def main():
        print("Checking Standalone Pure Tasks...")
        engine = TheusEngine()
        # Standalone tasks don't need registration if called by name or direct function
        print("1. Running Standalone Add (10, 20)...")
        res = await engine.execute(standalone_add, 10, 20)
        print(f"   Result: {res['result']} (Expected 30)")
        if res['result'] == 30:
            print("✅ Standalone Smoke Test Passed.")
        else:
            print("❌ Standalone Smoke Test Failed.")

    asyncio.run(main())
