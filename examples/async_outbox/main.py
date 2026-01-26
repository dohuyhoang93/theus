
import asyncio
import os
import sys
import time
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from context import DemoSystemContext, DemoDomainContext
from database import init_db, get_connection, insert_outbox_event
import processes # Register processes

from theus.engine import TheusEngine
# from demo_async_outbox.mock_engine import MockTheusEngine as TheusEngine # Reverted to Real Engine

async def main():
    print("=== THEUS ASYNC/OUTBOX DEMO ===")
    
    # 1. Init DB
    init_db()
    
    # 2. Setup Context (Dict for V3 Compatibility)
    domain = {
        "active_tasks": {}, 
        "outbox_buffer": [], 
        "sync_ops_count": 0,
        "async_job_result": ""
    }
    
    class SimpleContext:
        def __init__(self, d): 
            self.domain = d
            self.domain_ctx = d 
            # MOCK V3 OUTBOX (Shim)
            # Since Rust binding seems to swallow messages in this env, we rely on Python shim.
            self.outbox = self.MockOutbox()
            
        class MockOutbox:
            def __init__(self):
                self._msgs = []
            def add(self, msg):
                self._msgs.append(msg)
            def drain(self):
                msgs = list(self._msgs)
                self._msgs.clear()
                return msgs
                
        def to_dict(self):
             # Return full state for Engine Init
             return {"domain": self.domain}
        
    ctx = SimpleContext(domain)
    
    # 3. Setup Engine
    engine = TheusEngine(context=ctx, strict_mode=True)
    
    # DEBUG: Attach worker EARLY
    relay_buffer = []
    def relay_worker(msg):
        print(f"[Relay] Received from Engine: {msg.topic}")
        relay_buffer.append(msg)
    
    # Check if attach_worker exists
    if hasattr(engine, 'attach_worker'):
        engine.attach_worker(relay_worker)
        print("[System] Relay Worker Attached.")
    else:
        # --- Initialize Outbox Queue in Domain ---
        if 'outbox_queue' not in domain:
            domain['outbox_queue'] = []
    
    # 3. Create & Run Engine
    engine = TheusEngine(context=ctx)
    engine.register(processes.p_spawn_background_job)
    engine.register(processes.p_do_sync_work)
    engine.register(processes.p_await_job)
    engine.register(processes.p_prepare_outbox_event)
    engine.register(processes.p_log_blindness)
    engine.register(processes.p_log_success)
    
    # 3.1 Inject Signal (Test Flux Capability)
    print("\n[Test] Injecting 'cmd_start_outbox' signal...")
    try:
        engine.compare_and_swap(
            engine.state.version, 
            signal={'cmd_start_outbox': True}
        )
        print("[Test] Signal Injected.")
    except Exception as e:
        print(f"[Test] Signal Injection Failed: {e}")
    
    # --- Execute Workflow ---
    print("\n--- Start Workflow (Threaded) ---")
    loop = asyncio.get_running_loop()
    
    basedir = os.path.dirname(os.path.abspath(__file__))
    workflow_path = os.path.join(basedir, "workflow.yaml")
    
    # Run in thread pool to avoid blocking main loop
    # engine.execute_workflow is blocking rust call (internally manages tasks)
    future = loop.run_in_executor(None, engine.execute_workflow, workflow_path)
    
    # Wait for completion (Non-blocking await)
    await future
    print("--- End Workflow ---")

    # --- System Outbox Relay (State-Based) ---
    print("\n--- System Outbox Relay (Strict Logic) ---")
    
    # 1. Read Immutable State
    final_state = engine.state # Getter returns latest PyObject wrapper
    # Access domain safely
    domain_proxy = final_state.domain
    # FrozenDict -> dict
    final_domain = domain_proxy.to_dict() if hasattr(domain_proxy, 'to_dict') else domain_proxy
    
    relay_buffer = final_domain.get('outbox_queue', [])
    
    # Write to SQLite
    if relay_buffer:
        print(f"[Relay] Found {len(relay_buffer)} msgs in Domain State.")
        print("[Relay] Persisting to SQLite...")
        
        conn = get_connection()
        for m in relay_buffer:
            # m is OutboxMsg
            try:
                payload_str = m.payload
                if not isinstance(payload_str, str):
                     payload_str = json.dumps(payload_str)
            except:
                payload_str = str(m.payload)
                
            insert_outbox_event(conn, m.topic, payload_str)
        conn.commit()
        conn.close()
        print("[Relay] Persistence Complete.")
        
        # 2. Atomic Cleanup (CAS)
        # We must clear the queue to prevent re-processing
        print("[Relay] Clearing State Queue (Atomic CAS)...")
        current_ver = final_state.version
        
        # Prepare Delta (Partial Update)
        delta_domain = {'outbox_queue': []}
        
        try:
            engine.compare_and_swap(current_ver, data={'domain': delta_domain})
            print("[Relay] Queue Cleared.")
        except Exception as e:
             print(f"[Relay] Cleanup Failed (CAS Mismatch): {e}")

    else:
        print("[Relay] No messages in Domain State.")

    
    print("\n[Verification] Final State:")
    # Helper to print safe
    from helpers import get_attr
    print(f"  Sync Ops: {get_attr(ctx, 'domain.sync_ops_count')}")
    print(f"  Async Result: {get_attr(ctx, 'domain.async_job_result')}")
    # Buffer is no longer in domain!
    # print(f"  Buffer (Should be empty): {get_attr(ctx, 'domain.outbox_buffer')}")

if __name__ == "__main__":
     asyncio.run(main())
