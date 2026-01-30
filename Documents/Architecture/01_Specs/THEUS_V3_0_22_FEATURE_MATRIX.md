# Theus v3.0.22 Feature Matrix & API Reference

**Ngày lập báo cáo:** 2026-01-30
**Phiên bản:** v3.0.22
**Trạng thái:** Production Ready (Verified 107/107 Tests)

Tài liệu này liệt kê chi tiết toàn bộ các tính năng và API mà Theus Framework cung cấp, cùng với tình trạng triển khai thực tế trong mã nguồn.

---

## 1. Core Engine (`theus.engine`)
Trung tâm điều phối của hệ thống, quản lý Context, Transactions và tích hợp Rust Core.

| Feature / API | Signature | Mô tả | Trạng thái | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| **Constructor** | `TheusEngine(...)` | Khởi tạo Engine với Context, Audit Config. | ✅ **Stable** | Hỗ trợ `strict_mode`, `strict_cas`. |
| **Workflow** | `execute_workflow(yaml)` | Chạy quy trình Flux định nghĩa trong YAML. | ✅ **Stable** | Sử dụng Rust Flux Engine. |
| **Process Exec** | `execute(func, ...)` | Thực thi một Process đơn lẻ (Atomic). | ✅ **Stable** | Hỗ trợ Backoff/Retry tự động. |
| **Parallel Exec** | `execute_parallel(...)` | Chạy Process song song (mô hình Worker). | ✅ **Verified** | Fix `heavy` zone propagation (v3.1.2). |
| **Register** | `register(func)` | Đăng ký Process và validate Contract. | ✅ **Stable** | Kiểm tra Semantic Firewall. |
| **Transaction** | `transaction()` | Tạo transactional scope (ContextGuard). | ✅ **Stable** | Zero Trust Architecture. |
| **CAS** | `compare_and_swap(...)` | Commit trạng thái (Optimistic Lock). | ✅ **Stable** | Hỗ trợ Deep Merge & Delta Replay. |
| **State Access** | `engine.state` | Truy cập trạng thái hiện tại (Read-Only). | ✅ **Stable** | Trả về `RestrictedStateProxy`. |
| **Heavy Access** | `engine.heavy` | Truy cập bộ quản lý bộ nhớ lớn. | ✅ **Stable** | Trả về `ManagedAllocator`. |

## 2. Contracts & Decorators (`theus.contracts`)
Định nghĩa hành vi và cam kết (contract) của các Process theo triết lý POP.

| Decorator | Tham số chính | Mô tả | Trạng thái | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| `@process` | `inputs`, `outputs` | Khai báo I/O, Side-effects của hàm. | ✅ **Stable** | Bắt buộc cho mọi Process. |
| **Semantic** | `SemanticType` | Enum: `PURE`, `EFFECT`, `GUIDE`. | ✅ **Stable** | Dùng để phân loại Process. |

## 3. Data Structures & Context (`theus.structures`, `theus.context`)
Các cấu trúc dữ liệu cơ bản và đối tượng ngữ cảnh.

| Class / API | Mô tả | Trạng thái | Ghi chú |
| :--- | :--- | :--- | :--- |
| `ManagedAllocator` | Quản lý Shared Memory (NumPy/SHM). | ✅ **Stable** | Zero-Copy, Zombie GC (v3.1.2). |
| `StateUpdate` | Object trả về để yêu cầu update state. | ✅ **Stable** | Dùng trong `examples/async_outbox`. |
| `BaseSystemContext` | Lớp cơ sở cho System Context. | ✅ **Stable** | Expose tại `theus.__init__`. |
| `HeavyZoneWrapper` | Wrapper giúp truy cập Heavy Zone (`ctx.heavy`). | ✅ **Stable** | Hỗ trợ `__getattr__` (dot access). |
| `ContextGuard` | Proxy bảo vệ Context trong Transaction. | ✅ **Stable** | Chặn truy cập trái phép (Zero Trust). |

## 4. Parallelism (`theus.parallel`)
Cung cấp các Strategy để thực thi song song.

| Class | Mô tả | Trạng thái | Ghi chú |
| :--- | :--- | :--- | :--- |
| `ProcessPool` | Pool đa tiến trình (Multiprocessing). | ✅ **Stable** | Default trên Windows/NumPy < 2.0. |
| `InterpreterPool` | Pool Sub-Interpreters (PEP 554). | ⚠️ **Exp** | Chỉ hoạt động trên Python 3.14 + Extension hỗ trợ. |
| `ParallelContext` | Context rút gọn gửi cho Worker. | ✅ **Stable** | Picklable, tối ưu cho serialization. |

## 5. Interoperability (`theus.interop`)
Các công cụ tích hợp với hệ sinh thái Python bên ngoài.

| Feature | API | Mô tả | Trạng thái | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| **JSON Encoder** | `TheusEncoder` | Serialize Proxy sang JSON tốc độ cao. | ✅ **Stable** | Nhanh hơn 3.25x so với cast dict. |
| **Pydantic** | `Mapping.register` | Hỗ trợ Pydantic v2 validate trực tiếp. | ✅ **Stable** | Đăng ký tại `__init__`. |

## 6. Audit System (`theus.audit`)
Hệ thống giám sát và ghi nhật ký hoạt động (Rust Core tích hợp).

| Feature | Mô tả | Trạng thái |
| :--- | :--- | :--- |
| **Audit Ring Buffer** | Bộ đệm vòng ghi log hiệu năng cao (Zero-Allocation). | ✅ **Stable** |
| **Schema Gatekeeper** | Kiểm tra Schema trước khi cam kết transaction. | ✅ **Stable** |
| **Level Configuration** | Cấu hình mức độ log (Info/Warn/Error). | ✅ **Stable** |

---

## Tổng kết
Theus v3.1.22 cung cấp khoảng **25 APIs công khai** chính, bao phủ toàn bộ vòng đời phát triển ứng dụng Agentic:
1.  **Định nghĩa:** Contracts (Decorator).
2.  **Thực thi:** Engine, Transaction, Workflow.
3.  **Dữ liệu lớn:** ManagedAllocator (Heavy Zone).
4.  **Tích hợp:** Encoder, Pydantic.
5.  **Vận hành:** Audit, Parallel Pool.

Toàn bộ các tính năng lõi (Core) và an toàn (Safety) đều đã được kiểm chứng (Verified) và đánh dấu là **Stable**. Tính năng Sub-Interpreter đang ở mức **Experimental** do phụ thuộc vào sự hỗ trợ của nền tảng.
