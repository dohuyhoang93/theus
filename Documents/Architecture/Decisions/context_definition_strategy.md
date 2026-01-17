# ADR: Chiến lược Định nghĩa Context - Code-First vs Schema-First

**Trạng thái:** Đề xuất / Phân tích
**Ngày:** 22/12/2025
**Tác giả:** Theus AI & User

## 1. Bối cảnh
Trong Theus, `Context` là trái tim của hệ thống. Hiện tại (v2.1), chúng ta sử dụng phương pháp **Manual Code-First**: Developer viết class Python sử dụng `@dataclass`, sau đó hệ thống sinh ra `schema.yaml` (nếu cần).

**Vấn đề:**
*   Việc viết `dataclass` đôi khi rườm rà (boilerplate), dễ sai sót (ví dụ: dùng mutable default `list = []`).
*   Khó khăn cho các Non-Coder (BA, System Architect) muốn định nghĩa cấu trúc dữ liệu mà không biết Python.
*   Nhu cầu phát sinh: Tự động sinh code từ YAML (`schema > code`) để giảm tải.

Tuy nhiên, việc chuyển hoàn toàn sang Schema-First cũng có rủi ro tạo ra một hệ thống cứng nhắc hoặc phụ thuộc quá nhiều vào "Magic". Chúng ta cần một phân tích đa chiều.

## 2. Các Hướng Tiếp cận (Options)

### Phương án A: Code-First (Hiện tại)
*   **Cách làm:** Viết Python (`class AppDomain...`), dùng Theus CLI để export ra YAML làm tài liệu.
*   **Ưu điểm:**
    *   **DX Tuyệt vời:** IDE hỗ trợ 100% (Autocomplete, Refactoring, Find Usages).
    *   **Tự nhiên:** Dev cảm thấy thân thuộc, không cần học syntax mới.
    *   **Linh hoạt:** Có thể viết custom method/property trong class ngay lập tức.
*   **Nhược điểm:**
    *   Verbosity: Phải viết nhiều dòng import, type hinting.
    *   Rủi ro lỗi cú pháp Python dẫn đến crash Runtime.

### Phương án B: Static Schema-First (Code Generation)
*   **Cách làm:** Viết `schema.yaml`. Chạy lệnh `theus schema code` để sinh file `context.py`.
*   **Ưu điểm:**
    *   **Chuẩn hóa:** Cấu trúc YAML đơn giản, dễ kiểm soát, tránh lỗi sơ đẳng (mutable defaults).
    *   **Đa ngôn ngữ:** File YAML có thể dùng để sinh code cho Rust, JS client...
*   **Nhược điểm:**
    *   **Quy trình 2 bước:** Sửa YAML -> Chạy CMD -> Có Code. Nếu quên chạy CMD thì code và schema lệch nhau (Drift).
    *   **Code Rot:** File sinh ra thường khó đọc/khó sửa. Nếu Dev sửa tay vào file sinh ra, lần sinh tiếp theo sẽ ghi đè mất.

### Phương án C: Dynamic Schema-First (Metaprogramming)
*   **Cách làm:** Không có file `context.py`. Lúc chạy (`runtime`), Theus đọc YAML và tạo class động (`type('AppDomain', ...)`).
*   **Ưu điểm:**
    *   **Zero Boilerplate:** Không có file code thừa.
    *   **Always Sync:** Schema sửa là Code sửa theo ngay tức thì.
*   **Nhược điểm:**
    *   **Zero IDE Support:** IDE "mù", không gợi ý code (Dev code mò).
    *   **Performance:** Tốn thời gian khởi động để build class.
    *   **Magic:** Khó debug nếu Runtime tạo class sai.

## 3. Phân tích & Góc nhìn "Phi Nhị Nguyên"

Chúng ta không nên chọn *cực đoan* (chỉ Code hoặc chỉ Schema). Theus nên hỗ trợ cả hai như là các biểu hiện khác nhau của cùng một thực thể "Context".

*   **Góc nhìn của Dev:** Cần Code (để IDE hiểu).
*   **Góc nhìn của Architect/System:** Cần Schema (để nhìn tổng thể và tích hợp).

**Giải pháp đề xuất: "Code Scaffolding & Bi-directional Sync"**

Thay vì coi Schema là "nguồn chân lý duy nhất" đè bẹp Code, hay ngược lại, chúng ta coi Code là **Implementation**, Schema là **Contract**.

### Chiến lược Hybrid cho Theus v2.2:
1.  **Vẫn giữ Code-First là First-Class Citizen:** `context.py` là nơi Dev làm việc chính.
2.  **Tool `schema > code` hoạt động như Scaffolding (Giàn giáo):**
    *   Dùng để khởi tạo dự án nhanh.
    *   Dùng để update hàng loạt (ví dụ thêm field `X` vào 20 Context con).
    *   **QUAN TRỌNG:** Code sinh ra phải là **Human-Readable Python Code**, không phải "rác". Dev hoàn toàn có quyền làm chủ và chỉnh sửa nó sau khi sinh.
3.  **Hỗ trợ "Round-Trip" (Tương lai):** Sửa Code -> Update Schema. Sửa Schema -> Patch Code (không ghi đè mù quáng mà dùng AST để sửa).

## 4. Kết luận & Hành động

*   **Không dùng Dynamic (Option C):** Vì làm mất IDE support - điều tối kỵ của "Industrial DX".
*   **Chấp nhận Static Code Gen (Option B) ở mức độ "Tiện ích" (Utility):**
    *   Xây dựng lệnh `theus schema code` để sinh template.
    *   Nhưng KHÔNG bắt buộc quy trình build phải có nó.
*   **Giữ Core đơn giản (Option A):** Theus Engine vẫn load class Python bình thường, không quan tâm nó được viết tay hay máy sinh.

Điều này đảm bảo sự cân bằng: **Tự động hóa khi cần thiết, nhưng vẫn trao quyền kiểm soát code cho con người.**
