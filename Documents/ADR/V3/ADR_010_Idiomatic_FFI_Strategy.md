# ADR 010: Chiến Lược Cải Thiện Tính Tự Nhiên (Idiomatic) cho Python FFI

**Ngày tạo:** 2026-01-26  
**Trạng thái:** Đề xuất (Proposed)  
**Tác giả:** Antigravity (AI Assistant)  
**Phiên bản Theus:** v3.1 trở lên  

---

## 1. Bối Cảnh (Context)

Theus v3 sử dụng Rust Core để quản lý Transaction và Memory thông qua mô hình Supervisor (Proxy Pattern). Mặc dù mô hình này đảm bảo tính toàn vẹn dữ liệu (Data Integrity) và Zero-Copy, nhưng nó tạo ra "khoảng cách" với thói quen lập trình Python thông thường (Python Idioms).

Các vấn đề chính đã phát hiện trong quá trình phát triển Project Template (`scaffold`):

1.  **Lỗi kiểm tra kiểu (`isinstance Failure`):** `SupervisorProxy` hoạt động giống `dict` (Duck Typing) nhưng không kế thừa từ `dict`. Các thư viện bên thứ 3 (Pydantic, ORM) hoặc code kiểm tra `isinstance(obj, dict)` sẽ thất bại.
2.  **Lỗi Pickling (`Multiprocessing Failure`):** Các object Rust (như `FrozenDict`, `State`) không hỗ trợ protocol `pickle` mặc định, gây crash khi truyền sang worker process nếu không dùng metadata pattern thủ công.
3.  **Thiếu tích hợp Pydantic:** Engine yêu cầu `.to_dict()` để serialize, trong khi Pydantic dùng `.model_dump()`.

## 2. Phân Tích Kỹ Thuật (Technical Analysis)

### 2.1 Vấn Đề Proxy Type
Hiện tại:
```rust
#[pyclass]
pub struct SupervisorProxy { ... } 
// Python sees: <class 'theus_core.SupervisorProxy'> (extends object)
```
Python Developer mong đợi:
```python
isinstance(ctx.domain, dict) # True
```
Do `Proxy` không nằm trong MRO (Method Resolution Order) của `dict`, phép kiểm tra này luôn `False`.

### 2.2 Vấn Đề Pickling
Python `pickle` module cần phương thức `__reduce__` để biết cách tái tạo object ở phía bên kia (Process khác).
Object Rust chứa `Py<PyAny>` (Pointer tới Python Heap cục bộ). Pointer này **vô nghĩa** khi sang Process khác (Address Space khác). Do đó Pickling thất bại là đúng về mặt kỹ thuật, nhưng gây phiền toái về UX.

## 3. Đề Xuất Giải Pháp (Proposals)

Chúng ta không cần thay đổi kiến trúc Core, chỉ cần thêm lớp "Glue Code" (Keo dán) thông minh hơn.

### Giải Pháp A: "The Mockingbird Strategy" (Cho Proxy)

Thay vì trả về object Rust `SupervisorProxy` trực tiếp, ta sẽ wrap nó trong một class Python kế thừa từ `dict` (hoặc `MutableMapping`).

**Thiết kế:**
```python
# theus/structures.py
import collections

class PythonicProxy(collections.abc.MutableMapping):
    def __init__(self, rust_proxy):
        self._rust = rust_proxy
        
    def __getitem__(self, k): return self._rust[k]
    def __setitem__(self, k, v): self._rust[k] = v
    # ... delegate toàn bộ dunder methods ...
```

Hoặc nâng cao hơn (PyO3 Native Inheritance): Sử dụng `#[pyclass(extends=PyDict)]` để Rust Proxy thực sự là subclass của Dict. (Phương án này khó implement hơn do memory layout conflict nhưng hiệu năng cao hơn).

### Giải Pháp B: "The Auto-Pack Strategy" (Cho Pickling)

Implement `__reduce__` cho các struct quan trọng (`FrozenDict`, `SupervisorProxy`).

**Logic:**
1. Khi `pickle.dumps(proxy)` được gọi.
2. Rust `__reduce__` sẽ kiểm tra xem object bên dưới có phải là Shared Memory (Managed Allocator) không.
    *   **Nếu có (Heavy Zone):** Trả về metadata (SHM Name, Shape, Dtype).
    *   **Nếu không (Data Zone):** Trả về một bản copy `dict` thuần (Deepcopy).
3. Khi `pickle.loads` được gọi ở Worker:
    *   Tự động attach lại vào Shared Memory.
    *   Developer không cần viết code "Metadata Extraction" thủ công nữa.

### Giải Pháp C: "TheusModel Mixin" (Cho Pydantic)

Cung cấp sẵn base class chứa adapter cho Pydantic.

```python
# theus.models
class TheusStateModel(BaseModel):
    def to_dict(self):
        return self.model_dump()
        
    # Tự động wrap các nested model thành Proxy khi access?
    # (Có thể nghiên cứu sau)
```

## 4. Lộ Trình Triển Khai (Roadmap Suggestion)

Nếu được duyệt, các cải tiến này sẽ được đưa vào **Theus v3.3**:

1.  **Phase 1 (Easy wins):** 
    - Thêm `TheusStateModel` vào thư viện `theus`.
    - Implement `__reduce__` cơ bản cho `FrozenDict` (trả về error message hữu ích thay vì crash khó hiểu).
    
2.  **Phase 2 (Core Improvements):**
    - Nghiên cứu `PythonicProxy` wrapper để fix lỗi `isinstance`.

3.  **Phase 3 (Magic):**
    - Auto-Pickling cho Shared Memory (Zero-Code Parallelism).

## 5. Kết Luận

Việc Theus "không idiomatic" không phải là lỗi thiết kế, mà là hệ quả của việc ưu tiên **Safety & Performance** (Rust ownership). Tuy nhiên, bằng cách áp dụng các pattern Wrapper và Adapter (như đề xuất trên), ta có thể che giấu hoàn toàn sự phức tạp này, mang lại trải nghiệm "Code như Python thuần, Chạy như Rust".
