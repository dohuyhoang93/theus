import pytest
import asyncio
import os
import sys
import time
from theus.engine import TheusEngine
from theus.context import BaseSystemContext
from . import tasks

# Force Sub-interpreters for this entire suite
os.environ["THEUS_USE_PROCESSES"] = "0"

class TestSubInterpreterResilience:
    
    @pytest.fixture
    def engine(self):
        from theus.context import BaseGlobalContext, BaseDomainContext
        
        # [Fix] Provide required kwargs for BaseSystemContext
        g = BaseGlobalContext()
        d = BaseDomainContext()
        
        ctx = BaseSystemContext(global_ctx=g, domain=d)
        engine = TheusEngine(ctx, strict_guards=False) # Disable strict to simplify test setup
        # Register tasks
        engine.register(tasks.task_standard_echo)
        engine.register(tasks.task_heavy_compute)
        engine.register(tasks.task_large_payload)
        engine.register(tasks.task_conflict_generator)
        engine.register(tasks.task_crash_test)
        return engine

    @pytest.mark.asyncio
    async def test_case_standard_echo(self, engine):
        """
        [Case Mẫu] Kiểm tra hoạt động cơ bản: Gửi input -> Xử lý Worker -> Nhận Output.
        Chứng minh import StateUpdate không lỗi.
        """
        print("\n--- Test Standard Echo ---")
        result = await engine.execute("task_standard_echo", item="Hello World")
        
        # Verify result in engine state
        assert engine.state.data["last_echo"] == "Echo: Hello World"
        print("✅ Standard Echo Passed")

    @pytest.mark.asyncio
    async def test_case_related_heavy_compute(self, engine):
        """
        [Case Liên Quan] Xử lý tác vụ nặng không block main loop (logic).
        """
        print("\n--- Test Heavy Compute ---")
        start = time.time()
        # N=100000, should take a split second but process isolated
        await engine.execute("task_heavy_compute", n=100000)
        duration = time.time() - start
        
        result = engine.state.data["compute_result"]
        assert result > 0
        print(f"✅ Heavy Compute Passed (Duration: {duration:.4f}s)")

    @pytest.mark.asyncio
    async def test_case_edge_large_payload(self, engine):
        """
        [Case Biên] Payload lớn (10MB) đi qua ranh giới Sub-interpreter.
        Pickle serialization check.
        """
        print("\n--- Test Large Payload ---")
        # Python sub-interpreters share memory space, so this should not OOM
        await engine.execute("task_large_payload", size_mb=10)
        
        assert engine.state.data["heavy_payload"] == 10 * 1024 * 1024
        print("✅ Large Payload Passed")

    @pytest.mark.asyncio
    async def test_case_edge_error_handling(self, engine):
        """
        [Case Biên] Worker crash nên throw exception về Main process đúng cách.
        """
        print("\n--- Test Error Propagation ---")
        with pytest.raises(Exception) as excinfo:
            await engine.execute("task_crash_test")
        
        # The exact exception might be wrapped, but it should contain "Intentional Crash"
        assert "Intentional Crash" in str(excinfo.value)
        print("✅ Error Propagation Passed")

    @pytest.mark.asyncio
    async def test_case_conflict_concurrency(self, engine):
        """
        [Case Mâu Thuẫn] Nhiều worker cùng update 1 key.
        Engine (Main Process) phải handle serialization (tuần tự hóa) các StateUpdate.
        Lưu ý: Parallel Execution bản chất là async, nên await từng cái sẽ tuần tự.
        Để test conflict, ta phải dùng asyncio.gather.
        """
        print("\n--- Test Conflict / Concurrency ---")
        
        # 1. Spawn 5 workers at once
        coros = [
            engine.execute("task_conflict_generator", val=f"Worker-{i}")
            for i in range(5)
        ]
        
        # 2. Run concurrently
        # CAS logic in Engine.execute might retry or overwrite depending on strict_cas
        # Default strict_cas=False => Last writer wins usually, or Version mismatch logic handles it
        await asyncio.gather(*coros, return_exceptions=True)
        
        final_val = engine.state.data.get("race_key")
        print(f"Final Value: {final_val}")
        assert final_val.startswith("Worker-")
        print("✅ Concurrency Stress Passed")

    @pytest.mark.asyncio
    async def test_integration_chain(self, engine):
        """
        [Integration] Chạy chuỗi logic liên tiếp.
        Echo -> Compute -> LargePayload
        """
        print("\n--- Test Integration Chain ---")
        
        await engine.execute("task_standard_echo", item="Start")
        assert engine.state.data["last_echo"] == "Echo: Start"
        
        await engine.execute("task_heavy_compute", n=100)
        assert engine.state.data["compute_result"] > 0
        
        await engine.execute("task_large_payload", size_mb=1)
        assert engine.state.data["heavy_payload"] == 1024 * 1024
        
        print("✅ Integration Chain Passed")

if __name__ == "__main__":
    # Manual run support
    sys.exit(pytest.main(["-v", __file__]))
