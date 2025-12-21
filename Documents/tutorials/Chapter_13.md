# Chương 13: Web Integration - Theus as a Service

Theus sinh ra để làm Backend Service mạnh mẽ cho Web/API.

## 1. Mô hình 3 Lớp (Clean Architecture)

- **Lớp 1: Controller (FastAPI/Flask)**
    - Nhận HTTP Request.
    - Validate JSON body cơ bản (Pydantic).
    - Gọi Theus Engine.

- **Lớp 2: Service (Theus Engine)**
    - **Input Gate:** Validate nghiệp vụ phức tạp.
    - **Transaction:** Đảm bảo tính nguyên vẹn.
    - **Process:** Thực thi logic.

- **Lớp 3: Persistence (Database)**
    - Lưu Context xuống DB (Snapshot).

## 2. Dependency Injection (FastAPI)
```python
from fastapi import FastAPI, Depends
from theus.engine import TheusEngine

app = FastAPI()

# Singleton Engine (hoặc Per-Request tùy chiến lược)
_engine = None
def get_engine():
    global _engine
    if not _engine:
        # Init Engine, Load Recipes...
        _engine = TheusEngine(...) 
    return _engine

@app.post("/order")
def create_order(item_id: str, engine: TheusEngine = Depends(get_engine)):
    try:
        # Gọi Process. Mọi logic nghiệp vụ nằm trong Theus.
        # Controller chỉ là người chuyển phát.
        result = engine.run_process("create_order", item_id=item_id)
        return {"status": "success", "order": result}
        
    except AuditInterlockError as e:
        # Map lỗi Theus ra HTTP 400/500
        return {"error": "Policy Violation", "detail": str(e)}, 400
```

## 3. Stateless HTTP vs Stateful Context
HTTP là Stateless. Theus Context là Stateful.
Làm sao để kết hợp?
- **Load:** Đầu mỗi Request, load Context từ DB (bằng SessionID/UserID) vào Theus.
- **Run:** Chạy Theus Process.
- **Save:** Cuối Request, lưu Context (Data Zone) xuống DB.

Đây là mô hình **"Hydration/Dehydration"** kinh điển.

---
**Thực hành:**
Viết một API đơn giản bằng FastAPI nhận `POST /add-product` và gọi vào `add_product` process của Theus. Xử lý try/except để trả về mã lỗi HTTP hợp lý.