# Chương 12: Đặc tả Runtime Engine (Engine Internals)

---

## 12.1. Tổng quan Kiến trúc Runtime

Trong hệ sinh thái POP, Engine đóng vai trò là một **Process Virtual Machine (PVM)**. Nó không chỉ đơn thuần là trình chạy hàm (Function Runner), mà là hệ thống quản lý trọn vẹn vòng đời của dữ liệu và thực thi.

Kiến trúc Runtime bao gồm 3 lớp chính (3-Layer Architecture):
1.  **Transport Layer (Tầng Vận chuyển):** Chứa Context và Dữ liệu "câm" (Dumb Data).
2.  **Execution Layer (Tầng Thực thi):** Các hàm Process thuần túy thực hiện biến đổi dữ liệu.
3.  **Governance Layer (Tầng Quản trị):** Hệ thống "Cảnh sát" (Guard & Lock) quản lý quyền truy cập.

Mục tiêu của Engine là đảm bảo 3 tính chất: **Atomic** (Nguyên tử), **Consistent** (Nhất quán), và **Observable** (Có thể quan sát/Audit).

---

## 12.2. Cơ chế Quản trị Dữ liệu (Data Governance)

Để hiện thực hóa triết lý "Validation First" và "Contract Enforcement", Engine sử dụng 3 cơ chế kỹ thuật cốt lõi:

### **Cơ chế 1: The Airlock (Shadowing & Isolation)**
Engine sử dụng chiến lược **Implicit Shadowing** để cô lập Process khỏi dữ liệu gốc.
*   **Nguyên lý:** Process không bao giờ tương tác trực tiếp với Context gốc (Master Context).
*   **Cơ chế:**
    1.  Engine tạo bản sao nông (**Shadow Copy**) của Context.
    2.  Process thực hiện đọc/ghi trên bản sao này.
    3.  *Commit:* Nếu thành công, Engine merge thay đổi từ Shadow về Master.
    4.  *Rollback:* Nếu thất bại, Shadow bị hủy. Master giữ nguyên trạng thái cũ.
*   **Lợi ích:** Đảm bảo tính Transaction (Atomicity).

### **Cơ chế 2: The Customs Officer (Context Guard)**
Lớp trung gian `ContextGuard` chặn đứng mọi truy cập trái phép.
*   **Read Access Control:** Nếu Process truy cập `ctx.field` không có trong `input contract` -> `IllegalReadError`.
*   **Immutability Enforcement:** Các field input (không nằm trong output) được bọc bởi `FrozenList` hoặc `FrozenDict`. Mọi nỗ lực ghi đè sẽ bị chặn Exception ngay lập tức.

### **Cơ chế 3: The Vault (Context Locking)**
Bảo vệ dữ liệu khỏi các luồng (thread) bên ngoài.
*   **Trạng thái LOCKED (Mặc định):** Mọi thao tác ghi (`__setattr__`) từ bên ngoài đều bị từ chối.
*   **Trạng thái UNLOCKED:** Chỉ mở tạm thời trong phạm vi transaction của `engine.run_process()`.

---

## 12.3. Pipeline Thực thi Quy trình (Execution Pipeline - The Industrial Flow)

Khi lệnh `engine.run_process(name)` được gọi, một chuỗi 7 bước đồng bộ diễn ra, tích hợp chặt chẽ với hệ thống Audit:

1.  **Preparation (Chuẩn bị):**
    *   Lookup Process từ Registry.
    *   Phân tích Contract (`@process` decorator).
    *   Khởi tạo Transaction ID.

2.  **Input Gate (Cổng RMS - Audit Check):**
    *   **Audit Input:** Hệ thống kiểm tra dữ liệu đầu vào dựa trên `input_rules` trong `audit_recipe.yaml`.
    *   Nếu vi phạm Level S -> **Interlock** (Dừng ngay).
    *   Nếu vi phạm Level B/C -> Xử lý theo luật (Block/Log).

3.  **Isolation (Cách ly):**
    *   Tạo `ShadowContext`.
    *   Áp dụng `ContextGuard`.

4.  **Execution (Thực thi):**
    *   Thực thi hàm Process với inputs là `GuardedContext`.
    *   Catch Exception.

5.  **Output Gate (Cổng FDC - Audit Check):**
    *   **Audit Output:** Hệ thống kiểm tra thành phẩm đầu ra dựa trên `output_rules`.
    *   Bảo vệ hệ thống khỏi dữ liệu lỗi (Garbage Out).
    *   Phát hiện các bất thường (Anomaly) trước khi commit.

6.  **Delta Tracking & Commit:**
    *   So sánh trạng thái trước/sau (Diffing).
    *   Merge thay đổi vào Master Context.

7.  **Clean-up (Dọn dẹp):**
    *   Đóng Transaction.

---

## 12.4. Khả năng Mở rộng (Extensibility)

Engine được thiết kế để hỗ trợ:
1.  **Middleware Support:** Cho phép chèn các hook (Pre/Post-process) để đo lường hiệu năng (`PerformanceMonitor`) hoặc kiểm tra ràng buộc dữ liệu (`DataValidator`) mà không cần sửa code nghiệp vụ.
2.  **Scientific Computing:** Engine là **Data-Agnostic**. Nó quản lý `numpy.ndarray` hay `torch.Tensor` tốt như quản lý `dict` thông thường, hỗ trợ các bài toán tính toán ma trận phức tạp.

---

## 12.5. Các Giới hạn & Phân loại An toàn (Limitations & Safety Types)

Để cân bằng giữa An toàn và Tốc độ phát triển (Developer Velocity), POP chấp nhận một số thỏa hiệp:

### **Giới hạn Kỹ thuật**
1.  **Overhead:** Cơ chế Shadowing tốn tài nguyên CPU/RAM (~5-10% overhead).
2.  **Python Limits:** `FrozenList` chỉ bảo vệ ở mức ứng dụng. Một lập trình viên cố tình dùng C-extension vẫn có thể bypass.

### **Phân loại An toàn theo Kiểu dữ liệu (Safety by Type)**
Engine bảo vệ các loại dữ liệu ở mức độ khác nhau:

*   **Nhóm 1: Tuyệt đối An toàn (Immutable Primitives)**
    *   `int`, `float`, `str`, `tuple`.
    *   Không thể sửa nội tại (In-place mutation). Luôn an toàn.
*   **Nhóm 2: Được Bảo vệ (Managed Containers)**
    *   `list`, `dict`.
    *   Được Guard tự động chuyển thành `FrozenList`/`FrozenDict`. An toàn cao.
*   **Nhóm 3: Rủi ro (Unmanaged Mutable Objects)**
    *   `dataclass`, `numpy.ndarray`, `torch.Tensor`.
    *   Guard chỉ trả về tham chiếu gốc. Nếu Process gọi `array.append()` hoặc sửa nội tại object, Guard **không thể can thiệp**.
    *   *Khuyến nghị:* Hạn chế dùng Mutable Object cho State quan trọng, hoặc phải tự kỷ luật.
