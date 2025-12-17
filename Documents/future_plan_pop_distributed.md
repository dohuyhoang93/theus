# 🔮 Dự án POP Distributed (Future Vision)

> **Trạng thái:** Kế hoạch Độc lập (Standalone Project Plan)
> **Tương quan:** Tách biệt hoàn toàn khỏi `pop-sdk` hiện tại.
> **Mục tiêu:** Xây dựng lớp Orchestration Mesh cho các node POP Monolith.

---

## 🟥 **1. Tầm nhìn: Distributed Mesh**

Dự án này sẽ xây dựng một lớp "Vỏ bọc" (Wrapper Layer) để kết nối hàng nghìn instance `pop-sdk` đơn lẻ lại với nhau.

**Điểm cốt lõi:**
*   `pop-sdk` (Core) vẫn giữ nguyên là Single-Node, Stateless, High-Performance Monolith.
*   `pop-distributed` (Mesh) là lớp keo dính mạng giao tiếp.

### **1.1. Thách thức Hệ phân tán**
*   Mạng không tin cậy.
*   Độ trễ và Băng thông.
*   Đồng thuận trạng thái (Distributed Consensus).

### **1.2. Chiến lược Actor Model**
*   Mỗi POP Node được coi là một "Mega-Actor".
*   Giao tiếp qua Protocol riêng (gRPC/Zenoh).
*   Không chia sẻ bộ nhớ (No Shared Memory).

---

## 🟦 **2. Các Mô hình Triển khai (Roadmap)**

### **Phase 1: The Compute Grid (MapReduce)**
*   Mô hình Master-Worker cổ điển.
*   Dùng để xử lý Batch Job lớn (Vision Processing, AI Training).
*   Master chia Context thành Shards -> Gửi Worker -> Worker trả Delta.

### **Phase 2: The Service Mesh (SAGA)**
*   Mô hình Peer-to-Peer cho Enterprise.
*   Hỗ trợ Transaction phân tán (Distributed Transaction).
*   Cơ chế Bù trừ (Compensation Logic) khi một Node thất bại.

---

## 🟧 **3. Công nghệ Dự kiến**
*   **Core:** Rust (để đảm bảo performance mạng).
*   **Transport:** QUIC / gRPC.
*   **Consensus:** Raft (hoặc dùng Redis/Etcd làm external state store).

---
*Tài liệu này được tách ra từ đặc tả POP SDK để đảm bảo sự tập trung của dự án chính vào chất lượng Robust Monolith.*
