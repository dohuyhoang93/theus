# Theus v3.0 Migration Audit & Feature Matrix
**Date:** 2026-01-15
**Status:** VERIFIED & DEEP DIVE COMPLETE.
**Purpose:** Comprehensive inventory of existing mechanics, planned mutations, and new safety guarantees.

---

# 1. Cơ chế Cốt lõi (Core Mechanisms)

| Cơ chế (Mechanism) | Trạng thái v2.2.6 (Chi tiết) | Thay đổi trong v3.0 (Evolution) | An toàn (Safety Guarantee) |
| :--- | :--- | :--- | :--- |
| **Audit System** | **Multi-Level:** S(Stop), A(Abort), B(Block), C(Count). <br> **Dual-Threshold:** Cảnh báo (Min) -> Chặn (Max). <br> **Strategy:** Tích lũy (Default) hoặc Reset-on-Success. | **System Log (Ring Buffer).** Logic không đổi nhưng chuyển xuống Rust. Tốc độ ghi log audit cực nhanh, không block luồng chính. | Audit Log là "Append-Only". Không thể bị xóa/sửa bởi Process (Data Race Free). |
| **Workflow** | **Pipeline:** Chuỗi tuần tự đơn giản. <br> **Flux:** Điều phối phức tạp (If/Else/Loop) dựa trên User Code. | **Rust FSM (Strict).** <br> Pipeline và Flux được thống nhất thành Graph. Điều kiện rẽ nhánh (Flux) được đánh giá bởi Expression Engine an toàn. | FSM State là Atomic. Không bao giờ có 2 Process cùng chuyển trạng thái FSM cùng lúc. |
| **CLI & Init** | `theus init`. Tạo scaffold project. | **Smart Templates.** Template riêng cho Async AI Agent. | N/A |
| **Strict Mode** | Cờ `strict_mode=True`. Chặn truy cập trái phép bằng Exception. | **Type System Enforcement.** `Strict Mode` không còn là option lúc chạy, mà là **Default Compiles**. Vi phạm quyền truy cập sẽ bị chặn ngay từ lúc load process. | Compile-time check mạnh hơn Runtime check. |
| **Context Storage** | `dict` (Mutable). | **Immutable Struct (Arc<State>).** | **Multi-Version Concurrency Control (MVCC).** Reader không bao giờ bị block bởi Writer. |

---

# 2. Cơ chế An toàn Song song (Parallel Safety Mechanisms)

Đây là những bổ sung quan trọng cho v3 để xử lý bài toán **Async/Parallel** mà v2 chưa từng đối mặt.

| Vấn đề (Risk) | Giải pháp v3.0 (Solution) | Cơ chế Kỹ thuật (Technical Detail) |
| :--- | :--- | :--- |
| **Data Race** (2 process cùng ghi 1 biến) | **Atomic CAS (Compare-And-Swap).** | Process không ghi thẳng giá trị. Process gửi `StateUpdate(old_version, new_value)`. Engine chỉ chấp nhận nếu `old_version` khớp hiện tại. Nếu không -> Retry/Error. |
| **Inconsistent Writes** (Ghi đè giá trị) | **Transaction Isolation (Snapshot Isolation).** | Mỗi Process nhìn thấy một "Snapshot" cố định của dữ liệu lúc bắt đầu. Mọi thay đổi chỉ được merge khi commit. |
| **Memory Safety** (Truy cập vùng nhớ đã giải phóng) | **Rust Ownership & Borrow Checker.** | Không thể xảy ra Use-After-Free. Rust compiler đảm bảo biến `Local` sống đúng scope, `Global` sống đúng vòng đời App. |
| **Deadlock** (Khóa chéo) | **Lock-Free Reads / Timeout Writes.** | Read luôn là Lock-free (nhờ Immutability). Write dùng `RwLock` có timeout. Engine sẽ giết process nào giữ lock quá lâu. |

---

# 3. Tính năng Mới (New Features Inventory)

### 🌟 3.1. Heavy Zone (Vùng Tải Trọng)
*   Mô tả: Lưu trữ Tensor/Model lớn.
*   **An toàn:** Dùng `Arc<RwLock<T>>` nội bộ. Cho phép nhiều Reader đọc cùng lúc mà không copy.

### 🌟 3.2. Transactional Outbox
*   Mô tả: Ghi Intent thay vì thực thi IO.
*   **An toàn:** Đảm bảo "At-least-once delivery". Nếu Process crash trước khi commit, Intent không bao giờ được gửi đi (tránh gửi mail rác).

### 🌟 3.3. Hierarchical Scopes
*   Mô tả: Phân quyền `domain.user.*`.
*   **An toàn:** Engine chặn ghi đè chéo (Cross-write) giữa các module không liên quan.

### 🌟 3.4. Async Native & Dual-Mode
*   Mô tả: Hỗ trợ `async def`.
*   **An toàn:** Engine dùng `Tokio::spawn` cho Async và `Rayon` cho Sync, đảm bảo không bao giờ block Event Loop chính (tránh treo hệ thống).

### 🌟 3.5. Sub-Interpreter (Experimental)
*   Mô tả: True Parallelism.
*   **An toàn:** Mỗi Interpreter có GIL riêng. Shared Data phải đi qua kênh giao tiếp an toàn (Memory Channel), không share state trực tiếp.

---

# 4. Thay đổi về Mô hình 3 Trục (The 3-Axis Mutations)

| Trục | Biến đổi v3.0 |
| :--- | :--- |
| **Data Zone** | **Immutable Heap Struct**. Source of Truth. |
| **Signal Zone** | **Tokio Channels**. Real-time Event Stream. |
| **Meta Zone** | **System Log**. Hidden & Protected. |
| **Heavy Zone** | **Shared Reference Zone**. Generic `Arc<T>`. |
| **Local Layer** | **Lifecycle Scope**. Auto-drop. |
| **Global Layer** | **Arc<State>**. Transactional Commit. |
| **Pure Semantic** | **Input Firewall**. Cấm thấy Signal/Meta. |
| **Effect Semantic** | **Outbox Only**. Cấm IO trực tiếp. |

---

# 📊 Tổng kết

Bản rà soát này đã bổ sung đầy đủ các cơ chế "ngầm" tinh vi của v2 (Audit Thresholds, Flux/Pipeline distinctions) và giải trình chi tiết cách v3 đảm bảo an toàn bộ nhớ trong môi trường song song (CAS, Snapshot Isolation, Rust Ownership).
