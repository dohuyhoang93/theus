# Chương 6: Tổ chức Mã nguồn (Code Organization & Project Structure)

---

## 6.1. Bảy Nguyên Tắc Tổ Chức Code (The 7 Organization Principles)

Một dự án POP chuẩn mực cần tuân thủ 7 nguyên tắc cấu trúc sau (theo Spec Chapter 6):

1.  **Feature Modules:** Code được chia theo nghiệp vụ (Domain/Feature), không chia theo loại file (Model/View/Controller). Mỗi module tự chứa `context`, `processes`, `local`.
2.  **Registry Tách Biệt:** Cơ chế mapping `string_name -> function` phải nằm riêng, cho phép load động (Plugin Architecture).
3.  **Engine Độc Lập:** Workflow Runner chịu trách nhiệm đọc file cấu hình, validate, execute và trace. Nó không chứa logic nghiệp vụ.
4.  **Adapters ở Vỏ Ngoài:** Các driver giao tiếp phần cứng/DB (IO-bound) phải nằm ở layer ngoài cùng, không được lẫn vào core logic.
5.  **Schema Versioning:** Mỗi Domain Context phải có version. Thay đổi cấu trúc = Tăng version.
6.  **Audit & Logging:** Engine chịu trách nhiệm snapshot dữ liệu trước/sau mỗi Process.
7.  **Local Context Isolation:** Local Context chỉ sống trong phạm vi module/process, không được export ra ngoài.

---

## 6.2. Cấu Trúc Thư Mục Tiêu Chuẩn (Standard Project Structure)

Đây là bản vẽ quy hoạch "đô thị POP" tiêu chuẩn:

```
pop_project/
├── engine/                 # Khu vực Hạ tầng (Infrastructure)
│   ├── runner          # Workflow Executor
│   ├── registry        # Process Registry
│   └── loader          # Config Loader & Validator
├── adapters/               # Khu vực Giao tiếp (IO Layer)
│   ├── camera_adapter
│   ├── database_adapter
│   └── network_adapter
├── modules/                # Khu vực Nghiệp vụ (Domain Core)
│   ├── vision/             # Feature: Xử lý ảnh
│   │   ├── context     # Domain Context Definitions
│   │   ├── processes   # Business Logic Types
│   │   └── tests       # Unit Tests
│   └── robot_control/      # Feature: Điều khiển Robot
│       ├── context
│       └── processes
├── workflows/              # Khu vực Kịch bản (Configuration)
│   ├── deployment.yaml
│   └── simulation.yaml
└── schemas/                # Khu vực Hợp đồng (Data Contracts)
    └── context_v1.json
```

---

## 6.3. Giải phẫu một Module (Module Anatomy)

Một module POP gọn gàng sẽ bao gồm 3 thành phần chính:

### 1. `context` (The Data Shape)
Định nghĩa cấu trúc dữ liệu đầu vào/đầu ra của module.
*   *Nhiệm vụ:* Công khai cấu trúc dữ liệu cho hệ thống.

### 2. `processes` (The Logic Types)
Chứa các hàm xử lý thuần túy (Pure Functions) hoặc hàm gọi Adapter.
*   *Nhiệm vụ:* Biến đổi context. Phải đăng ký với Registry.

### 3. `local` (The Internals - Optional)
Chứa các helper function, local context definitions.
*   *Nhiệm vụ:* Ẩn giấu sự phức tạp nội bộ.

---

## 6.4. Cơ chế Registry & Wiring (Chi tiết)

Để kết nối các Module rời rạc thành một hệ thống sống động, POP sử dụng **Registry Pattern**. Đây không chỉ là dictionary, mà là "bảng điều khiển trung tâm" của hệ thống.

### Nguyên lý hoạt động:
1.  **Registration:** Mỗi Process khi khởi động sẽ tự đăng ký mình với Registry bằng một `Unique String Key` (ví dụ: `vision.detect_face`).
2.  **Configuration:** File Workflow (YAML/JSON) chỉ chứa chuỗi ký tự (String), không chứa code.
3.  **Resolution:** Tại Runtime, Engine đọc chuỗi từ Workflow -> Tra cứu trong Registry -> Lấy được Function thực thi.

> **Lợi ích:** Tách biệt hoàn toàn việc "Code làm gì" (Logic) và "Khi nào chạy" (Orchestration).

---

## 6.5. Ví dụ Minh họa (Implementation Examples)

### Python (Idiomatic POP)
```python
# engine/registry.py
REGISTRY = {}
def register(name):
    def wrapper(func):
        REGISTRY[name] = func
        return func
    return wrapper

# modules/vision/processes.py
from engine.registry import register

@register("vision.load_image")
def load_image(ctx, env):
    # Adapter call via env
    ctx.raw_bytes = env['camera'].capture()
    return ctx
```

### Rust (System Level)
```rust
// modules/vision/src/processes.rs
pub fn load_image(ctx: &mut Context, env: &Env) -> Result<()> {
    let bytes = env.camera.capture()?;
    ctx.raw_bytes = Some(bytes);
    Ok(())
}
// Registry in main.rs will map "vision.load_image" -> function pointer
```

---

## 6.6. Chiến lược Kiểm thử (Testing Strategy)

Tổ chức code theo POP mang lại lợi thế kiểm thử cực lớn nhờ tính cô lập.

### 1. Unit Test (Process Isolation)
Mỗi Process là một hàm thuần túy hoặc hàm cô lập.
*   **Cách test:** Mock `Input Context`, gọi hàm, assert `Output Context`. Không cần mock cả hệ thống DB hay Server.

### 2. Contract Test (Schema Validation)
Đảm bảo Process tuân thủ đúng cam kết về dữ liệu.
*   **Cách test:** Dùng `Pydantic` hoặc `JSON Schema` để validate Input/Output context của từng Process.

### 3. Integration Test (Workflow Simulation)
Chạy thử toàn bộ một chuỗi Process với Mock Adapters.
*   **Cách test:** Load file YAML thực tế -> Chạy qua Mock Environment -> Kiểm tra kết quả cuối cùng.

---

## 6.7. Các Dấu hiệu Sai lầm (Anti-Patterns)

Nếu thấy dự án xuất hiện các dấu hiệu sau, cấu trúc POP đã bị phá vỡ:

1.  **Circular Dependency:** Module A gọi Module B, B gọi lại A. (Giải pháp: Đẩy phần chung xuống `core` hoặc `common`).
2.  **Hidden Coupling:** Process trong Module A lén đọc file config của Module B.
3.  **Fat Adapter:** Adapter chứa logic nghiệp vụ (ví dụ: Adapter SQL chứa câu lệnh `if user.is_active`).
4.  **Leakage:** Local Context bị truyền từ Process này sang Process khác.
