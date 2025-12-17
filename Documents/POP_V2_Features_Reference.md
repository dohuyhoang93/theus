# Tài liệu Tham chiếu Tính năng POP SDK V2 (Feature Reference)

> **Phiên bản:** 2.0 (Industrial Native Refactor)
> **Trạng thái:** Production Ready (Linear Mode)
> **Ngôn ngữ:** Python (Native First)

Tài liệu này tổng hợp chi tiết các cơ chế và tính năng hiện có trong `python-pop-sdk` phiên bản mới nhất.

---

## 1. Kiến trúc Cốt lõi (Core Architecture)

### 1.1. Native First Strategy
*   **Mô tả:** POP V2 loại bỏ hoàn toàn sự phụ thuộc vào Rust Bridge phức tạp của V1. SDK hiện tại là **100% Thuần Python**.
*   **Lợi ích:** Dễ cài đặt (`pip install`), dễ debug, tương thích tuyệt đối với các thư viện AI (PyTorch, TensorFlow).
*   **Cơ chế:** Engine chạy trực tiếp trên Thread của Python, sử dụng các cơ chế quản lý bộ nhớ của Python (Reference Counting).

### 1.2. Process-Oriented (Hướng Quy trình)
*   **Tách biệt Data & Logic:**
    *   **Context (Data):** Chỉ chứa dữ liệu (Dataclasses), không chứa methods.
    *   **Process (Logic):** Pure Functions, chỉ nhận Context vào và trả Context ra.
*   **Minh bạch (Transparency):** Mọi sự thay đổi trạng thái hệ thống đều phải thông qua Process được khai báo.

---

## 2. Hệ thống Cấu hình "Holy Trinity"

POP V2 quản lý hệ thống thông qua bộ 3 file YAML, đảm bảo nguyên tắc "Config as Code".

### 2.1. Schema Config (`specs/context_schema.yaml`)
*   **Chức năng:** Định nghĩa cấu trúc dữ liệu của toàn bộ hệ thống (Single Source of Truth).
*   **Cơ chế:** SDK đọc file này và có thể validate dữ liệu tĩnh (Static Check).
*   **Ví dụ:**
    ```yaml
    context:
      domain:
        user: { name: string, age: integer }
    ```

### 2.2. Audit Recipe (`specs/audit_recipe.yaml`)
*   **Chức năng:** Định nghĩa các luật lệ (Rules) để kiểm soát chất lượng dữ liệu và an toàn hệ thống.
*   **Cơ chế:** Tách biệt hoàn toàn logic kiểm tra (Validation) ra khỏi code nghiệp vụ (Business Logic).
*   **Đặc điểm:** Hỗ trợ kế thừa luật (Rule Inheritance) và ghi đè (Override).

### 2.3. Workflow Config (`workflows/*.yaml`)
*   **Chức năng:** Định nghĩa dòng chảy thực thi (Execution Flow).
*   **Cơ chế:** Hiện tại hỗ trợ mô hình **Linear** (Tuần tự).
*   **Ví dụ:** `steps: [ "validate_input", "calculate_score" ]`

---

## 3. Hệ thống Kiểm toán Công nghiệp (Industrial Audit System)

Đây là tính năng đột phá nhất của V2, lấy cảm hứng từ tiêu chuẩn sản xuất (RMS/FDC).

### 3.1. Hai Cổng Kiểm Soát (Dual Gates)
Mỗi Process khi chạy sẽ bị chặn bởi 2 cổng:
1.  **Input Gate (RMS Check):** Kiểm tra nguyên liệu đầu vào trước khi Process chạy.
    *   *Mục đích:* Ngăn chặn Process chạy với dữ liệu rác (Garbage In).
2.  **Output Gate (FDC Check):** Kiểm tra thành phẩm đầu ra sau khi Process chạy xong (nhưng trước khi Commit).
    *   *Mục đích:* Ngăn chặn dữ liệu lỗi lan ra hệ thống (Garbage Out).

### 3.2. Bốn Cấp độ Nghiêm trọng (Severity Internal Standards)
Hệ thống xử lý lỗi theo 4 cấp độ chuẩn hóa:

| Cấp độ | Tên gọi | Hành động của Engine | Ý nghĩa |
| :--- | :--- | :--- | :--- |
| **S** | **Serious / Stop** | **Interlock** (Dừng ngay lập tức, Rollback). | Lỗi an toàn, bảo mật. |
| **A** | **Abort / Warning** | Cảnh báo. Dừng nếu vi phạm quá ngưỡng (Threshold). | Lỗi hiệu năng, tài nguyên. |
| **B** | **Block / Batch** | Giữ lại (Hold) để xử lý sau. | Lỗi quy trình (nghi ngờ). |
| **C** | **Continue / Info** | Ghi Log (có Throttling: 1, 10, 100...) và chạy tiếp. | Thông tin gỡ lỗi. |
| **I** | **Ignore / Bypass** | Không Check, Không Log. | Bypass cho Complex Objects (Adapter/Tensor). |

---

## 4. Engine & Quản lý Trạng thái (State Management)

### 4.1. Atomic Transaction (Giao dịch Nguyên tử)
*   **Cơ chế:**
    1.  Trước khi Process chạy, Engine tạo một lớp vỏ bảo vệ (`ContextGuard`).
    2.  Process chỉ thao tác trên bản nháp (Shadow Copy).
    3.  Nếu có lỗi (Exception hoặc Audit Violation Level S): Engine **Vứt bỏ** bản nháp. Context gốc không đổi.
    4.  Nếu thành công: Engine **Commit** bản nháp vào Context gốc.

### 4.2. Rollback
*   **Cơ chế:** Nhờ kiến trúc "Shadow Copy", việc Rollback đơn giản là không thực hiện bước "Merge" dữ liệu.

---

## 5. Công cụ CLI (Command Line Interface)

POP V2 cung cấp bộ công cụ dòng lệnh mạnh mẽ để tăng tốc phát triển.

### 5.1. `pop init <name>`
*   **Chức năng:** Khởi tạo dự án mới theo cấu trúc chuẩn V2.
*   **Kết quả:** Tạo thư mục `specs/`, `workflows/`, `src/` và các file mẫu.

### 5.2. `pop audit gen-spec`
*   **Chức năng:** Tự động quét code (`src/processes`) để tìm các Process và Input/Output của chúng.
*   **Kết quả:** Tạo file khung `specs/audit_recipe_gen.yaml`. Giúp Dev không phải viết YAML từ con số 0.

### 5.3. `pop audit inspect <process_name>`
*   **Chức năng:** Xem chi tiết các luật đang áp dụng lên một Process cụ thể.
*   **Hiển thị:** Danh sách Input Rules, Output Rules và Audit Level tương ứng.

---

## 6. Tổng kết

POP SDK V2 không chỉ là một thư viện, mà là một **Bộ khung Quản trị (Governance Framework)**. Nó giúp bạn code nhanh (nhờ Python) nhưng vẫn đảm bảo sự an toàn và kiểm soát khắt khe (nhờ Industrial Audit).
