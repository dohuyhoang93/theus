from tests.manual.parallel_lib import task_serial, task_parallel

if __name__ == "__main__":
    import asyncio
    from theus import TheusEngine

    async def run_smoke_test(label, env_updates):
        print(f"\n--- Testing Backend: {label} ---")
        import os
        for k, v in env_updates.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        
        engine = TheusEngine()
        engine.register(task_serial)
        engine.register(task_parallel)

        # Trigger lazy init
        await engine.execute(task_parallel, n=1000)
        
        backend = "Unknown"
        if hasattr(engine, "_parallel_pool") and engine._parallel_pool:
            backend = engine._parallel_pool.__class__.__name__
        
        print(f"Parallel Backend Active: {backend}")

        print("1. Running Serial Task...")
        res1 = await engine.execute(task_serial)
        print(f"   OK: PID={res1['pid']}, TID={res1['tid']}")

        print("2. Running Parallel Task...")
        res2 = await engine.execute(task_parallel)
        print(f"   OK: PID={res2['pid']}, TID={res2['tid']}")
        
        # Cleanup for next run
        engine.shutdown()

    async def main():
        from theus.parallel import INTERPRETERS_SUPPORTED
        
        print("Checking Parallelism Primitives (Automated CI Mode)...")
        
        # Mode A: Sub-interpreters (Force if supported)
        if INTERPRETERS_SUPPORTED:
            await run_smoke_test("Sub-interpreters", {
                "THEUS_FORCE_INTERPRETERS": "1",
                "THEUS_USE_PROCESSES": None
            })
        
        # Mode B: Processes (Force)
        await run_smoke_test("ProcessPool", {
            "THEUS_FORCE_INTERPRETERS": None,
            "THEUS_USE_PROCESSES": "1"
        })
        
        print("\n✅ Parallel Smoke Test Passed for all modes.")

    asyncio.run(main())
