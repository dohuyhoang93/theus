# Chapter 13: Service Layer Pattern (FastAPI Integration)

Theus is designed to be the "Iron Core" Service Layer for modern Web APIs (FastAPI, Flask, Django).
This aligns with **Domain-Driven Design (DDD)** and **Clean Architecture**.

> **🌟 Reference Implementation:**
> A complete, runnable FastAPI example is available at [`examples/fastapi_service`](../../../examples/fastapi_service). 
> We recommend Developer/AI Agents use this as the "Source of Truth" for scaffolding.

## 🚀 Quick Start (Running the Example)

You can run the reference implementation immediately:

```bash
# 1. Install Dependencies
pip install fastapi uvicorn requests

# 2. Run the Server (from project root)
# Windows (PowerShell)
$env:PYTHONPATH="."; python -m uvicorn examples.fastapi_service.main:app --port 8111 --reload

# Linux/Mac
PYTHONPATH=. python -m uvicorn examples.fastapi_service.main:app --port 8111 --reload
```

**Explore the API:**
*   **Swagger UI:** [http://127.0.0.1:8111/docs](http://127.0.0.1:8111/docs)
*   **Health Check:** `GET /health`
*   **Order API:** `POST /orders` (Business Logic)


## 1. 3-Layer Architecture Setup

Think of your codebase in 3 layers:

1.  **FastAPI (Controller):** Handles HTTP, JSON Parsing, Authentication (User Identity).
2.  **Theus (Service/Model):** Handles Business Logic, Transactionality, Safety Checks.
3.  **Context/DB (Persistence):** Storage.

## 2. The Dependency Injection Pattern

We recommend injecting the `TheusEngine` using FastAPI's Dependency Injection. This ensures efficient Singleton usage for the heavy Rust Core, while allowing per-request logic.

### Standard Scaffolding

See [`examples/fastapi_service/src/dependencies.py`](../../../examples/fastapi_service/src/dependencies.py) for the full implementation.

**Key Pattern:**
```python
# src/dependencies.py
from functools import lru_cache
from typing import Annotated
from fastapi import Depends
from theus import TheusEngine

# Singleton instance
_engine_instance: TheusEngine | None = None

def get_engine() -> TheusEngine:
    global _engine_instance
    if _engine_instance is None:
        # Initialize Context & Engine ONCE
        # ... initialization logic ...
        _engine_instance = TheusEngine(...)
    return _engine_instance
```

### Controller wiring

See [`examples/fastapi_service/main.py`](../../../examples/fastapi_service/main.py).

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from theus_core import AuditBlockError, ContextError

@app.post("/orders")
async def create_order(
    req: OrderRequest, 
    engine: Annotated[TheusEngine, Depends(get_engine)]
):
    try:
        # 1. Delegate Logic to Theus (Async)
        result = await engine.execute("create_order", **req.dict())
        return {"status": "success", "data": result}
        
    except AuditBlockError as e:
        # 2. Map Policy Violations to 429/403
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        
    except ContextError:
        # 3. Map Concurrency Conflicts to 409
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Retry required")
```

## 3. Background Worker Pattern (GUI/Long Tasks)

For long-running workflows that shouldn't block the HTTP response, use `asyncio` or a Task Queue context.

```python
import asyncio

class TheusWorker:
    def __init__(self, engine: TheusEngine):
        self.engine = engine
        self.queue = asyncio.Queue()

    async def _run(self):
        while True:
            workflow = await self.queue.get()
            try:
                # v3.0+: engine.execute_workflow is Async & Non-blocking
                await self.engine.execute_workflow(workflow)
            except Exception as e:
                print(f"Workflow Error: {e}")
            finally:
                self.queue.task_done()

    async def submit(self, workflow_path: str):
        await self.queue.put(workflow_path)
```

## 4. Stateless vs Stateful

Web APIs are Stateless. Theus Context is Stateful.
**Strategy: Context Hydration.**

In `create_order` process:
1.  **Read:** Load user data from DB into `ctx.domain` (if not cached).
2.  **Process:** Logic via Theus.
3.  **Write:** Save `ctx.domain` delta back to DB (if using persistent DB).

Ideally, wrap the `await engine.execute` call in a DB Transaction scope to ensure Theus Commit aligns with DB Commit.

---

## 🤖 AI Assistant Guide

If you are an AI Coding Assistant (Cursor, Copilot, etc.), follow these rules when implementing Theus in Web APIs:

1.  **Strict Type Hints:** Always type hint the Engine dependency (`engine: TheusEngine`).
2.  **Exception Mapping:** NEVER catch generic `Exception` unless for 500 logging. ALWAYS strictly catch `AuditBlockError` (Policy) and `ContextError` (CAS Conflict) and map them to appropriate HTTP codes.
3.  **Singleton Pattern:** Verify that `TheusEngine` is initiated only once (Global/Singleton) to avoid reloading Rust Core/Models on every request.
4.  **Async/Await:** Since v3.0, Theus is Async-Native. Always use `await engine.execute(...)`.

---

**Exercise:**
Run the example service:
`uvicorn examples.fastapi_service.main:app --reload`
Then try to spam the `/orders` endpoint to trigger the `AuditBlockError` (if configured).
