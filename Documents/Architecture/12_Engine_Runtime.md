# Chương 12: Theus Microkernel - Trái tim máy (Engine Internals)

---

## 12.1. Tổng quan Kiến trúc Microkernel

Engine của Theus không còn là một "Process Runner" đơn thuần. Nó được thiết kế như một **Microkernel** (Hệ điều hành hạt nhân nhỏ) chuyên dụng cho tự động hóa.

Mục tiêu của Theus Microkernel là quản lý sự **hỗn loạn** của thế giới thực thông qua sự **kỷ luật** của máy tính.

### Kiến trúc 3 Lớp (The 3-Layer Architecture)

```mermaid
graph TD
    UserCode[User Processes] -->|Calls| Kernel API
    
    subgraph "Theus Microkernel"
        Governance[Layer 3: Governance (Cảnh sát)]
        Execution[Layer 2: Execution (Dây chuyền)]
        Transport[Layer 1: Transport (Kho vận)]
    end
    
    Governance -->|Enforces| Execution
    Execution -->|Mutates| Transport
```

1.  **Transport Layer (Vận chuyển):** Nơi chứa Context và dữ liệu "câm". Nhiệm vụ duy nhất là lưu trữ đúng chỗ.
2.  **Execution Layer (Thực thi):** Nơi chạy các Process. Đây là "cơ bắp" của hệ thống.
3.  **Governance Layer (Quản trị):** Nơi chứa các luật lệ (Guard, Lock, Auditor). Đây là "bộ não" kiểm soát an toàn.

---

## 12.2. Cơ chế Quản trị Dữ liệu: "The Iron Triangle"

Để đảm bảo an toàn tuyệt đối, Theus sử dụng bộ 3 cơ chế bảo vệ gọi là "Tam giác sắt":

### 1. The Airlock (Shadowing) - Cách ly
*   **Vấn đề:** Nếu cho Process sửa trực tiếp Context gốc (`Master Context`), khi Process lỗi giữa chừng, Context sẽ bị hỏng (Inconsistent State).
*   **Giải pháp:** Theus tạo một bản sao (**Shadow Context**) cho mỗi Process.
    *   Process chỉ được sửa bản sao.
    *   Nếu thành công: Kernel thực hiện **Atomic Commit** (Merge bản sao về bản gốc).
    *   Nếu thất bại: Kernel hủy bản sao. Bản gốc nguyên vẹn.

### 2. The Gatekeeper (Context Guard) - Kiểm soát
*   **Vấn đề:** Process cố tình đọc/ghi vào biến không được phép.
*   **Giải pháp:** Lớp `ContextGuard` bọc lấy Context.
    *   Nó chặn mọi truy cập không khai báo (Illegal Read/Write).
    *   Nó đóng băng (`Frozen`) các biến Input để đảm bảo Process không vô tình sửa tham số đầu vào.

### 3. The 3-Axis Matrix - Luật pháp
Core của việc kiểm soát nằm ở **Ma trận An toàn 3 Trục** (Xem Chương 4). Kernel không chỉ check tên biến, mà check giao điểm của:
*   **Zone:** (Data/Signal)
*   **Semantic:** (Input/Output)
*   **Layer:** (Global/Domain)

> **Ví dụ:** Nếu Process cố gắng khai báo `inputs=['sig_stop']` (Dùng Signal làm đầu vào), Kernel sẽ chặn ngay lập tức vì vi phạm nguyên tắc Determinism (Signal không ổn định để Replay).

---

## 12.3. Pipeline Thực thi Công nghiệp (Flux Engine Upgrade)

Trong phiên bản 2.1.4 (Flux Upgrade), Engine chuyển từ chế độ chạy danh sách tuyến tính (`Linear List`) sang chế độ thực thi đệ quy (`Recursive Execution`).

```python
def _execute_step(step):
    if is_process(step): execute_process(step)
    elif is_flux_if(step): resolve_condition_and_branch(step)
    elif is_flux_while(step): loop_until_false(step)
```

Mỗi thao tác (Process) vẫn tuân thủ dây chuyền 7 bước bảo mật của Microkernel:
(Lưu ý: Nếu không dùng Audit Recipe, Bước 2 và Bước 6 sẽ được bỏ qua - Zero Config Mode).

1.  **Registry Lookup:** Tìm Process và Contract trong sổ cái.
2.  **Input Audit (Gate 1):** Kiểm tra Input Rules (nếu có) dựa trên Context hiện tại. Nếu vi phạm -> **Chặn ngay lập tức** (Fail Fast).
3.  **Shadowing & Transaction:** Mở khóa (Unlock) cho Process, khởi tạo Transaction, chuẩn bị cơ chế Shadow Copy.
4.  **Guard Injection:** Bọc Context bằng `ContextGuard` để kiểm soát truy cập (chỉ cho phép Input/Output đã khai báo).
5.  **Execution (Unsafe Zone):** Chạy code Python của người dùng với `guarded_ctx`.
6.  **Output Audit (Gate 2) - Critical:**
    *   Kiểm tra kết quả Output trên bản sao Shadow (**TRƯỚC khi Commit**).
    *   **Level A (Interlock):** Crash -> Dừng hệ thống.
    *   **Level B (Block):** Soft Fail -> Raise `AuditBlockError`.
7.  **Atomic Commit / Rollback:**
    *   Nếu OK: `tx.commit()` (Ghi đè Shadow vào Context thật).
    *   Nếu Lỗi/Block: `tx.rollback()` (Hủy Shadow, Context toàn vẹn).

---

## 12.4. Các mức độ An toàn (Safety Tiers)

Theus chia dữ liệu thành 3 hạng mục để bảo vệ:

### Tier 1: Primitives (Tuyệt đối an toàn)
*   `int`, `str`, `tupe`, `bool`.
*   Python không cho phép sửa nội tại (Immutable). Theus bảo vệ 100%.

### Tier 2: Managed Structures (An toàn cao)
*   `List`, `Dict`.
*   Theus tự động chuyển đổi thành `TrackedList` và `FrozenList`.
*   Nếu bạn thử `ctx.settings.append(1)` trên một Input List, bạn sẽ nhận lỗi `ContractViolation`.

### Tier 3: Foreign Objects (Cần kỷ luật)
*   `numpy.array`, `torch.Tensor`, `CustomClass`.
*   Theus không thể can thiệp vào bộ nhớ C++ của Numpy.
*   **Cảnh báo:** Developer phải tự ý thức không được sửa nội tại (mutate inplace) các object này nếu chúng là Input.

---

## 12.6. Autopilot: Tính năng Tự động Khám phá (Auto-Discovery)

Theus v2.1 được trang bị "Crawler" thông minh (`engine.scan_and_register`) để tự động hóa việc đăng ký Process. Không còn cần `engine.register_process()` thủ công.

### Cơ chế hoạt động (The Internal Mechanics)
Engine thực hiện quy trình "4 bước" để tìm kiếm và xác nhận Process:

1.  **Quét File (File Walking):**
    *   Duyệt đệ quy cây thư mục `src/` (bỏ qua `__pycache__`).
    *   Lọc lấy tất cả các file có đuôi `.py`.

2.  **Nạp Động (Dynamic Loading):**
    *   Sử dụng `importlib.util` để load file thành module Python tại Runtime (Lazy Loading).
    *   Không yêu cầu file phải được import trong `main.py`.

3.  **Thanh tra (Deep Inspection):**
    *   Sử dụng `inspect.getmembers()` để liệt kê mọi object trong module.

4.  **Nhận diện (Identification Protocol):**
    *   Engine chỉ chấp nhận các hàm thỏa mãn 2 điều kiện:
        1.  `inspect.isfunction(obj)`: Là hàm.
        2.  `hasattr(obj, '_pop_contract')`: **Có decorator `@process`**.
    *   *Lợi ích:* Các hàm helper, utility hay class thông thường sẽ tự động bị bỏ qua, không làm rác Registry.

```python
# Bootstrapping trở nên cực kỳ đơn giản
engine = TheusEngine(context)
engine.scan_and_register("src") # Done!
```

---

## 12.7. Kết luận
Theus Microkernel không sinh ra để làm chậm code của bạn. Nó sinh ra để **bảo hiểm** cho code của bạn. Có Theus, bạn có thể tự tin deploy logic phức tạp mà không sợ hiệu ứng cánh bướm (Butterfly Effect) làm sập hệ thống.
