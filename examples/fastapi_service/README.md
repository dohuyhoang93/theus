# Theus FastAPI Service Example

This is a reference implementation of the **Service Layer Pattern** (Chapter 13) using **FastAPI** + **Theus Engine**.

## Features
*   **Dependency Injection**: Efficient `TheusEngine` Singleton management.
*   **Async/Await**: Non-blocking business logic execution.
*   **Strict Contracts**: Using `StateUpdate` for precise granular updates.
*   **Exception Mapping**: Converting `AuditBlockError` and `ContextError` to HTTP 4xx codes.

## How to Run

1.  **Navigate to Framework Root:**
    ```bash
    cd <path_to_theus_framework>
    ```

2.  **Install Dependencies:**
    ```bash
    pip install fastapi uvicorn
    ```

3.  **Start Server:**
    ```bash
    # Windows
    $env:PYTHONPATH="."; python -m uvicorn examples.fastapi_service.main:app --port 8111 --reload

    # Linux / Mac
    PYTHONPATH=. python -m uvicorn examples.fastapi_service.main:app --port 8111 --reload
    ```

4.  **Open Browser:**
    Go to: [http://127.0.0.1:8111/docs](http://127.0.0.1:8111/docs)

## Project Structure
*   `main.py`: FastAPI Controller & Routes.
*   `src/dependencies.py`: Engine Factory & DI Logic.
*   `src/processes.py`: Pure Business Logic (POP).
*   `src/context.py`: Domain Models.
