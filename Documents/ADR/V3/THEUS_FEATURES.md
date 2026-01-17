# Các Tính Năng Cốt Lõi Của Theus Framework v3.0 (Phân tích từ Mã nguồn)

## 1. Process-Oriented Programming (POP)
- **Decorator `@process` (`theus/contracts.py`)**: Chuyển đổi hàm Python thành "tiến trình" (process) có quản lý.
- **Phân loại Ngữ Nghĩa (`SemanticType`)**:
  - `PURE`: Chỉ được đọc Domain/Input, không side-effects, bị tường lửa ngữ nghĩa chặn truy cập Signal/Meta.
  - `EFFECT`: Được phép truy cập Global và thực hiện I/O.
- **Process Contracts (`contracts.py` & `engine.py`)**: Định nghĩa Input/Output rõ ràng (Glob pattern). Engine tự động ánh xạ giá trị trả về (`return`) vào State dựa trên contract.

## 2. Quản lý Trạng thái & Đồng thời (State & Concurrency)
- **3-Axis Context Model (`src/structures.rs`, `src/zones.rs`)**:
  - **Lớp (Layers)**: Domain (nghiệp vụ), Global (hệ thống), Local (cục bộ).
  - **Vùng (Zones)**:
    - **DATA**: Dữ liệu chuẩn, có Transaction Log & Rollback.
    - **HEAVY**: Dữ liệu lớn (Tensor, Ảnh), Zero-copy, Write-Through (không Rollback dữ liệu, chỉ tham chiếu).
    - **SIGNAL**: Sự kiện, Ephemeral (biến mất sau xử lý).
- **Optimistic Concurrency Control (CAS - `src/engine.rs`)**: Sử dụng thuật toán Compare-and-Swap dựa trên Version vector để cập nhật trạng thái an toàn trong đa luồng.
- **Transactional Consistency (`src/delta.rs`, `src/engine.rs`)**: Hỗ trợ Rollback tự động khi có Process Failure (ngoại trừ Heavy Zone).
- **Strict Mode (`src/guards.rs`)**: Bắt buộc tính bất biến (Immutability), chặn sửa đổi trực tiếp trên object trạng thái (phải qua Transaction/CAS).

## 3. Hệ thống Quy trình làm việc (Workflow Engine - Flux DSL)
- **Flux DSL (`src/fsm.rs`)**: Ngôn ngữ định nghĩa quy trình dựa trên YAML.
  - `flux: while`: Vòng lặp điều kiện.
  - `flux: if/else`: Rẽ nhánh logic.
  - `flux: run`: Gom nhóm (nesting) các bước.
- **Safety Limits**: Giới hạn số lượng operation tối đa (`THEUS_MAX_LOOPS`) để ngăn vòng lặp vô hạn.
- **Hybrid Execution**: Hỗ trợ chạy các process đồng bộ và bất đồng bộ (`asyncio`) trong cùng một workflow thông qua cơ chế FSM (Pending -> Running -> WaitingIO).

## 4. Hệ thống Audit & Chính sách (Audit System)
- **4 Cấp độ Audit (`src/audit.rs`)**:
  - **S (Stop)**: Dừng hệ thống ngay lập tức khi vi phạm.
  - **A (Abort)**: Hủy bỏ thao tác hiện tại.
  - **B (Block)**: Chặn thao tác khi vượt quá ngưỡng (Threshold).
  - **C (Count)**: Chỉ đếm, không can thiệp.
- **Threshold System**: Hỗ trợ `threshold_max` (chặn) và `threshold_min` (cảnh báo). Có chế độ `reset_on_success` để phát hiện lỗi chập chờn (flaky).
- **Audit Ring Buffer**: Log tuần hoàn hiệu năng cao trong bộ nhớ (Memory-based), thread-safe.

## 5. Eventing & Tích hợp (Eventing & Integration)
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

## 6. Song song Thực sự (True Parallelism - Experimental)
- **Sub-interpreters Support (`theus/parallel.py`)**:
  - Tận dụng **PEP 554** (Python 3.14+) để thực thi song song thực sự (True Parallelism) trên đa nhân CPU, loại bỏ hoàn toàn GIL bottleneck.
  - **Capability**: Đã kiểm thử và xác nhận hoạt động tốt với **Pure Python Processes** (các hàm tính toán thuần túy, không phụ thuộc vào Theus Core Extension).
  - **Limitation**: Hiện tại chưa hỗ trợ chia sẻ các object của Rust Core (như `Engine`, `Context`) sang sub-interpreter do hạn chế của PyO3 ABI trên Python 3.14 (sẽ khắc phục trong tương lai).
  - **Use Case**: Thích hợp nhất cho các tác vụ CPU-bound nặng (AI Inference, Image Processing, Math) chạy độc lập.
- **Engine API**: `InterpreterPool` tự động quản lý vòng đời và phân phối task.
