# Các Tính Năng Cốt Lõi Của Theus Framework v3.0.1 (Phân tích từ Mã nguồn)

## 1. Process-Oriented Programming (POP)
- **Decorator `@process` (`theus/contracts.py`)**: Chuyển đổi hàm Python thành "tiến trình" (process) có quản lý.
- **Phân loại Ngữ Nghĩa (`SemanticType`)**:
  - `PURE`: Chỉ được đọc Domain/Input, không side-effects, bị tường lửa ngữ nghĩa chặn truy cập Signal/Meta.
  - `EFFECT`: Được phép truy cập Global và thực hiện I/O.
  - `GUIDE`: Dùng cho các process hướng dẫn/điều phối, có quyền truy cập mở rộng.
- **`@process(parallel=True)`**: Đánh dấu function để chạy trong Parallel Pool. Engine tự động dispatch tới worker.
- **Process Contracts (`contracts.py` & `engine.py`)**: Định nghĩa Input/Output rõ ràng (Glob pattern). Engine tự động ánh xạ giá trị trả về (`return`) vào State dựa trên contract.

## 2. Quản lý Trạng thái & Đồng thời (State & Concurrency)
- **3-Axis Context Model (`src/structures.rs`, `src/zones.rs`)**:
  - **Lớp (Layers)**: Domain (nghiệp vụ), Global (hệ thống), Local (cục bộ).
  - **Vùng (Zones)** - 4 loại:
    - **DATA**: Dữ liệu chuẩn, có Transaction Log & Rollback.
    - **HEAVY**: Dữ liệu lớn (Tensor, Ảnh), Zero-copy, Write-Through (không Rollback dữ liệu, chỉ tham chiếu).
    - **SIGNAL**: Sự kiện, Ephemeral (biến mất sau xử lý). Prefix: `sig_`, `cmd_`.
    - **META**: Metadata hệ thống, thông tin context. Prefix: `meta_`.
- **Optimistic Concurrency Control (CAS - `src/engine.rs`)**: Sử dụng thuật toán Compare-and-Swap dựa trên Version vector để cập nhật trạng thái an toàn trong đa luồng.
- **Transactional Consistency (`src/delta.rs`, `src/engine.rs`)**: Hỗ trợ Rollback tự động khi có Process Failure (Yêu cầu tuân thủ **Copy-on-Write** cho Collections).
- **Zero-Copy & Strict Mode Strategy (V3)**:
  - **Zero-Copy Read**: Truy cập dữ liệu (Domain, Heavy) với tốc độ O(1) (bỏ qua Shallow Copy).
  - **Discipline Safety**: Do cơ chế Zero-Copy, việc sửa đổi trực tiếp (`in-place mutation`) là **KHÔNG AN TOÀN** (Bypass Rollback). Lập trình viên **BẮT BUỘC** sử dụng pattern `new = list(old)` (Copy-on-Write) để đảm bảo an toàn.

## 3. Advanced Conflict Resolution (`src/conflict.rs`)
- **Key-Level CAS**: `State.key_last_modified` - Fine-grained conflict detection thay vì global locking. Chỉ conflict khi 2 process cùng ghi vào **cùng một key**.
- **Exponential Backoff + Jitter**: `sleep(base * 2^retries) * rand(0.8..1.2)` - Tự động retry với delay tăng dần và random để tránh thundering herd.
- **Priority Ticket (VIP Locking)**: Sau 5 lần thất bại liên tiếp → process được cấp VIP holder, block tất cả request khác cho đến khi hoàn thành.
- **`ConflictManager`**: Module Rust quản lý toàn bộ conflict strategy, expose `report_conflict()` và `report_success()` API cho Python.

## 4. Managed Memory Subsystem (`src/shm.rs`, `src/shm_registry.rs`)
- **`engine.heavy.alloc(key, shape, dtype)`**: API tự động quản lý Shared Memory, không cần `try...finally {unlink()}`.
- **Namespace Format**: `theus:{session_uuid}:{pid}:{key}` - Không collision giữa các session/process.
- **Ownership Model**:
  - **Main = Owner**: Có quyền `unlink()` khi cleanup.
  - **Workers = Borrowers**: `SafeSharedMemory` chặn `unlink()`, chỉ được đọc.
- **Zombie Collector (`MemoryRegistry.scan_zombies()`)**: Startup scan, parse tên segment, kiểm tra PID còn sống không, unlink orphans tự động.
- **Rust Integration**: `shm_registry.rs` với PyO3 bindings, `Drop` trait đảm bảo cleanup.

## 5. Zero-Copy Parallelism (v3.2+)
- **Hybrid Zero-Copy Model**: >2x speedup cho heavy data workloads (>100MB).
- **`ctx.heavy` (Zero-Copy Zone)**: Shared Memory View thay vì dict thông thường.
  - **Write**: `alloc()` tạo named memory segment do Rust Core quản lý.
  - **Read**: Worker nhận **Read-Only** view, không copy bytes.
- **`ParallelContext`**: Context stripped-down cho workers:
  - `ctx.domain` (Copy of input args + domain state)
  - `ctx.heavy` (Zero-copy handle)
- **Smart Pickling**: Chỉ pickle metadata, không pickle big data.
- **Collision & Crash Safety**: Unique names per session/PID, Zombie Recovery nếu script crash.

## 6. Hệ thống Quy trình làm việc (Workflow Engine - Flux DSL)
- **Flux DSL (`src/fsm.rs`)**: Ngôn ngữ định nghĩa quy trình dựa trên YAML.
  - `flux: while`: Vòng lặp điều kiện.
  - `flux: if/else`: Rẽ nhánh logic.
  - `flux: run`: Gom nhóm (nesting) các bước.
- **Safety Limits**: Giới hạn số lượng operation tối đa (`THEUS_MAX_LOOPS`) để ngăn vòng lặp vô hạn.
- **Hybrid Execution**: Hỗ trợ chạy các process đồng bộ và bất đồng bộ (`asyncio`) trong cùng một workflow thông qua cơ chế FSM (Pending -> Running -> WaitingIO).

## 7. Hệ thống Audit & Chính sách (Audit System)
- **4 Cấp độ Audit (`src/audit.rs`)**:
  - **S (Stop)**: Dừng hệ thống ngay lập tức khi vi phạm.
  - **A (Abort)**: Hủy bỏ thao tác hiện tại.
  - **B (Block)**: Chặn thao tác khi vượt quá ngưỡng (Threshold).
  - **C (Count)**: Chỉ đếm, không can thiệp.
- **Threshold System**: Hỗ trợ `threshold_max` (chặn) và `threshold_min` (cảnh báo). Có chế độ `reset_on_success` để phát hiện lỗi chập chờn (flaky).
- **Audit Ring Buffer**: Log tuần hoàn hiệu năng cao trong bộ nhớ (Memory-based), thread-safe.

## 8. Eventing & Tích hợp (Eventing & Integration)
- **High-Speed SignalHub (`src/signals.rs`)**:
  - Sử dụng `tokio::broadcast` channel cho hiệu năng cao (Rust-based).
  - Mô hình Pub/Sub bất đồng bộ.
  - `SignalHub.publish()`: Gửi tin nhắn chuỗi (string-based signals).
- **Reliable Outbox Pattern (`src/structures.rs`, `src/engine.rs`)**: 
  - **Rust-Backed Integrity**: Toàn bộ logic Outbox được chuyển xuống Rust Core để đảm bảo tính toàn vẹn dữ liệu.
  - **Atomic Commit Guarantee**: Tin nhắn chỉ được phát đi (flush) khi và chỉ khi Transaction chính của Process thành công. Nếu Process lỗi hoặc Transaction rollback, tin nhắn Outbox cũng tự động bị hủy -> Ngăn chặn tuyệt đối "Phantom Messages".
  - **API**: `ctx.outbox.add(msg)` (Python) -> `OutboxCollector` (Rust).
- **Python-Rust Interop (`pyo3`)**:
  - **Tensor Guards (`src/tensor_guard.rs`)**: Wrapper đặc biệt cho Numpy/Torch tensors, cho phép tính toán trực tiếp (zero-copy arithmetic) trong khi vẫn ghi log truy cập.
  - **Shared Memory**: Trao đổi dữ liệu hiệu quả giữa Python và Rust Core.

## 9. True Parallelism (v3.2+ - Production Ready)
- **`InterpreterPool` (`theus/parallel.py`)** - Đã **tích hợp đầy đủ** vào `TheusEngine`:
  - Tận dụng **PEP 554** (Python 3.14+) Sub-Interpreters để bypass GIL hoàn toàn.
  - **`engine.get_pool()`**: Lazy-init pool, tự động quản lý vòng đời.
  - **`engine.execute_parallel(process_name, **kwargs)`**: Chạy process trong sub-interpreter.
  - **Fallback**: Tự động dùng `ProcessPool` (Multiprocessing Spawn) nếu sub-interpreters không khả dụng, hoặc set `THEUS_USE_PROCESSES=1`.

- **`@process(parallel=True)` Auto-Dispatch**:
  - Engine tự động nhận diện flag `parallel=True` và route execution tới `InterpreterPool`.
  - Worker nhận `ParallelContext` stripped-down: `ctx.domain` + `ctx.heavy` (zero-copy).

- **Hệ sinh thái hỗ trợ đầy đủ**:
  - **Managed Memory (§4)**: `engine.heavy.alloc()` cấp phát Shared Memory với namespace unique, Zombie Collector tự động cleanup.
  - **Zero-Copy (§5)**: `ctx.heavy` trong worker là **Read-Only Shared Memory View**, không copy bytes.
  - **Conflict Resolution (§3)**: Key-Level CAS + VIP Locking đảm bảo các parallel writes không conflict.

- **Verified Performance** (`tests/09_v3_2/test_subinterpreter_parallel.py`):
  - 4 tasks × 0.5s với 2 workers → hoàn thành trong ~1.0s (thay vì 2.0s sequential).
  - Speedup thực sự **2x** đã được kiểm chứng.

- **Use Case**: CPU-bound nặng (AI Inference, Matrix Ops, Image Processing) với dữ liệu lớn qua `ctx.heavy`.

---
