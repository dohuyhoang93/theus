# BÁO CÁO PHÂN TÍCH KỸ THUẬT TOÀN DIỆN: THEUS FRAMEWORK

**Dự án:** Theus
**Phiên bản phân tích:** v2.2.3
**Kiến trúc:** Hybrid (Rust Microkernel + Python Orchestrator)
**Mô hình:** Process-Oriented Programming (POP)
**Ngày báo cáo:** 10/01/2026

---

## 1. Tóm tắt Điều hành (Executive Summary)

**Theus** là một framework cấp công nghiệp (industrial-grade) hiện thực hóa tư tưởng **Lập trình Hướng Quy trình (POP)**. Dự án được thiết kế để giải quyết các vấn đề cốt lõi của phần mềm doanh nghiệp hiện đại: sự phức tạp của trạng thái (state complexity), kiểm soát tác dụng phụ (side-effects) và khả năng truy vết (auditability).

Điểm đặc biệt nhất của Theus là kiến trúc lai ghép: sử dụng **Rust** làm hạt nhân (Engine) để đảm bảo hiệu năng và tính đúng đắn của dữ liệu, trong khi sử dụng **Python** làm lớp giao tiếp để tận dụng tính linh hoạt và hệ sinh thái phong phú.

---

## 2. Kiến trúc Hệ thống & Cơ chế Lõi (Core Mechanics)

### 2.1. Mô hình Hybrid: Rust & Python
Hệ thống sử dụng `PyO3` và `Maturin` để tạo cầu nối FFI (Foreign Function Interface) hiệu suất cao.
*   **Rust Layer (`src/`)**: Đóng vai trò là "Microkernel". Chịu trách nhiệm quản lý bộ nhớ, thực thi Transaction, giám sát Audit và bảo vệ tính toàn vẹn dữ liệu.
*   **Python Layer (`theus/`)**: Đóng vai trò là "Orchestrator". Định nghĩa logic nghiệp vụ, luồng công việc (Workflow) và giao tiếp với các thư viện bên ngoài.

### 2.2. Phân vùng Bộ nhớ (Context Zones) - `src/zones.rs`
Hệ thống không coi mọi dữ liệu là như nhau. Dữ liệu được phân loại nghiêm ngặt theo **3-Axis Context Model**:
1.  **Data Zone:** Dữ liệu nghiệp vụ bền vững (Persistence). Được bảo vệ bởi Transaction.
2.  **Signal Zone (`sig_`, `cmd_`):** Dữ liệu sự kiện tạm thời (Transient). Dùng để kích hoạt chuyển đổi trạng thái FSM.
3.  **Meta Zone (`meta_`):** Dữ liệu chẩn đoán (Diagnostic). Bỏ qua các ràng buộc Transaction nặng nề.
4.  **Heavy Zone:** Dành cho dữ liệu lớn (Tensor, Image). Tối ưu hóa Zero-copy để tránh nghẽn băng thông bộ nhớ.

### 2.3. Transaction & Snapshot Isolation - `src/delta.rs`
Theus áp dụng mô hình cô lập Snapshot:
*   Mỗi Process khi chạy sẽ nhận một bản sao (hoặc Shadow) của dữ liệu.
*   Mọi thay đổi được ghi vào vùng đệm `Delta`.
*   Chỉ khi Process kết thúc thành công (không có Exception và vượt qua Audit), `Delta` mới được **Commit** vào Context gốc. Điều này đảm bảo tính nguyên tử (Atomicity) tuyệt đối.

### 2.4. Context Guards - `src/guards.rs`
Đây là cơ chế an ninh cốt lõi. Guard hoạt động như một Sandbox bao quanh Process. Nếu một Process cố gắng đọc/ghi vào vùng nhớ mà nó không khai báo trong Hợp đồng (Contract), Guard (viết bằng Rust) sẽ chặn ngay lập tức và ném lỗi `AccessDenied`. Điều này loại bỏ hoàn toàn các lỗi "side-effect" ngầm.

---

## 3. Hệ thống Audit Chủ động (Active Audit System)

Khác với logging thụ động, hệ thống Audit của Theus (trong `src/audit.rs`) tham gia trực tiếp vào luồng điều khiển.

### 3.1. Phân cấp Hành động (Action Hierarchy)
Hệ thống định nghĩa phản ứng dựa trên mức độ nghiêm trọng của vi phạm:
*   **Level S (Safety Interlock):** Dừng khẩn cấp toàn bộ hệ thống (`Emergency Stop`).
*   **Level A (Abort):** Dừng luồng quy trình hiện tại (Hard Stop).
*   **Level B (Block):** Từ chối Transaction hiện tại (Rollback) nhưng cho phép hệ thống tiếp tục hoạt động (Soft Stop/Retry).
*   **Level C (Campaign):** Chỉ ghi cảnh báo (Warning).

### 3.2. Cơ chế Ngưỡng Kép (Dual-Thresholds)
Sử dụng `AuditTracker` để theo dõi sức khỏe hệ thống theo thời gian:
*   **Min Threshold:** Cảnh báo sớm.
*   **Max Threshold:** Kích hoạt trừng phạt (Block/Abort).
*   **Flaky Detection:** Thông qua tham số `reset_on_success`, hệ thống có thể phát hiện các thành phần hoạt động chập chờn (lỗi không liên tục) để loại bỏ sớm.

---

## 4. Tổ chức Mã nguồn & "Quy hoạch Đô thị"

Dự án tuân thủ cấu trúc "Urban Plan" (`Documents/SPECS/06_Code_Organization.md`):

### 4.1. Phân tầng Rõ ràng
*   **`specs/`**: Chứa "Luật" (YAML config, Schema). Nơi duy nhất định nghĩa cấu trúc dữ liệu.
*   **`src/domain/`**: Chứa Logic nghiệp vụ. Áp dụng nguyên tắc **Colocation**: Class định nghĩa dữ liệu và Hàm xử lý nằm chung một file (Feature Vertical).
*   **`adapters/`**: "Cửa khẩu" giao tiếp với thế giới bên ngoài (I/O). Nơi duy nhất được phép import các thư viện side-effect (DB, Network).

### 4.2. Auto-Discovery
Không cần file `main.py` khổng lồ để kết nối các module. Engine tự động quét thư mục, tìm các hàm có decorator `@process` và đăng ký vào Global Registry.

---

## 5. Chất lượng Kỹ thuật & Bảo trì

### 5.1. Kiểm thử (Testing)
Bộ test (`tests/`) bao phủ rộng và sâu:
*   **Deep Leakage:** Kiểm tra rò rỉ bộ nhớ ở tầng sâu nhất.
*   **Zombie Proxy:** Đảm bảo không truy cập được dữ liệu đã cũ/hết hạn.
*   **Concurrency:** Kiểm chứng khả năng chịu tải đa luồng.

### 5.2. Cải tiến v2.2.3 (Release Notes)
Phiên bản mới nhất đã giải quyết vấn đề **Reference Cycle (Deadly Embrace)** giữa Python và Rust. Bằng cơ chế `forced cleanup` trong Transaction, hệ thống giờ đây an toàn tuyệt đối về bộ nhớ ngay cả trong chế độ nghiêm ngặt (`Strict Mode`), cho phép vận hành lâu dài (Long-running) mà không bị Memory Leak.

---

## 6. Kết luận

Framework **Theus** là một thành tựu kỹ thuật ấn tượng, kết hợp sự chặt chẽ của khoa học máy tính (Transaction, FSM, Safety) với thực tiễn phát triển phần mềm hiện đại.

**Khuyến nghị:**
*   Phù hợp cho các hệ thống: Tài chính (FinTech), Điều khiển Robot, AI Agents, và các hệ thống Backend phức tạp cần độ tin cậy cao.
*   Yêu cầu đội ngũ: Cần nắm vững tư duy POP (tư duy theo luồng dữ liệu) thay vì OOP truyền thống.

---
*Người lập báo cáo: Gemini CLI Agent*
