# Chương 2: Kiến trúc Hợp nhất (Theus Unified Architecture)

---

## 2.1. Định vị Đại chiến lược (Grand Strategy)

Theus không sinh ra để loại bỏ OOP hay thay thế Clean Architecture. Theus sinh ra để quản lý **Sự Phức tạp của Dòng chảy (Flow Complexity).**

Trong một hệ thống tự động hóa hiện đại (`Modern Automation System`), Theus đề xuất mô hình **Kiến trúc Kép (Dual Architecture)**:

1.  **Macro-Architecture (Vĩ mô - Theus):**
    *   Quản lý luồng dữ liệu (Data Flow).
    *   Điều phối quy trình (Orchestration).
    *   Đảm bảo an toàn và Audit (Governance).
    *   *Analogy:* Đây là hệ thống giao thông, đèn tín hiệu, luật lệ giao thông.

2.  **Micro-Architecture (Vi mô - OOP/Functional):**
    *   Thực hiện các tác vụ cụ thể bên trong từng Process.
    *   Quản lý driver thiết bị, thuật toán xử lý ảnh.
    *   *Analogy:* Đây là động cơ xe, bánh xe, hệ thống phanh của từng chiếc xe.

> **Key takeaway:** Theus quản lý "ai làm gì lúc nào", còn OOP quản lý "làm như thế nào".

---

## 2.2. Sự Cộng sinh (Symbiosis Patterns)

### Pattern 1: Theus bọc OOP (The Wrapper)
Khi bạn có một thư viện OOP phức tạp (ví dụ `class CameraDriver`), đừng cố viết lại nó bằng Theus Process. Hãy bọc nó lại.

*   **OOP Layer:** `driver = CameraDriver(port=0)` (Giữ state private, xử lý logic phần cứng).
*   **Theus Adapter:** Một hàm Process `capture_image(ctx)` sẽ gọi `driver.read()` và đưa kết quả vào Context.

### Pattern 2: Theus tiêm Clean Arch (The Injection)
Clean Architecture chia hệ thống thành các vòng tròn đồng tâm. Theus nằm ở vòng ngoài cùng (Frameworks & Drivers) nhưng lại điều khiển luồng đi vào trung tâm (Entities).

*   **Entities:** Định nghĩa `Order`, `Product` (Pure Python Class).
*   **Use Cases:** Các Process của Theus đóng vai trò là Use Case Interactor.
*   **Context:** Đóng vai trò là DTO (Data Transfer Object) di chuyển giữa các lớp.

---

## 2.3. Thang đo Trừu tượng (Abstraction Scale)

Theus cho phép bạn chọn mức độ chặt chẽ tùy theo giai đoạn dự án:

### Level 1: Duck Typing (Prototyping)
*   Process gọi trực tiếp `env.camera.read()`.
*   *Ưu điểm:* Code cực nhanh, sửa đổi dễ dàng.
*   *Nhược điểm:* Khó test, dễ runtime error.

### Level 2: Strict Typing (Production)
*   Sử dụng `Protocol` để định nghĩa Interface cho `env`.
*   Process chỉ tương tác với Interface.
*   *Ưu điểm:* Type-safe, hỗ trợ IDE tốt.

### Level 3: Theus Kernel Injection (Enterprise)
*   Context được quản lý bởi Kernel.
*   Mọi truy cập I/O đều bị chặn bởi Security Policy.
*   *Ưu điểm:* An toàn tuyệt đối, zero-trust.

---

## 2.4. Kết luận

Mô hình **Unified Architecture** xóa bỏ ranh giới xung đột.
*   Bạn dùng OOP để **xây dựng công cụ** (Build Tools).
*   Bạn dùng Theus để **vận hành dây chuyền** (Operate Pipeline).

Sự kết hợp này tạo ra một hệ thống vừa mạnh mẽ (nhờ OOP) vừa minh bạch và dễ quản lý (nhờ Theus).
