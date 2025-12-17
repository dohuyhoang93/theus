# 📘 **POP Specification — Tập 3: Chiến lược Tái định vị & Kỷ luật An toàn**

> **Phiên bản:** Draft 2.0 (Realignment Strategy)
> **Tác giả:** Do Huy Hoang
> **Ngày:** 13/12/2025
> **Tóm tắt:** Tài liệu này bổ sung cho đặc tả POP SDK, tập trung vào chiến lược **"Robust Monolith First"**. Chúng ta từ bỏ cách tiếp cận "ôm đồm" Distributed để tập trung hoàn thiện 3 trụ cột của một hệ thống nghiệp vụ sâu: Khả năng mở rộng nội tại (Scalable Composition), Kỷ luật An toàn Bất biến (Immutable Governance), và Sự minh bạch của Runtime (Transparent Engine).

---

# **Chương 15 - Khả năng Tương thích Mở rộng (Scalable Composition)**
*(Thay thế hoàn toàn chương "Hệ thống Phân tán" cũ)*

## 🟥 **1. Định vị lại: POP là Kernel, không phải Cloud Framework**

POP SDK xác định rõ ranh giới của mình: Nó là một **Process Virtual Machine** tối ưu cho việc vận hành logic nghiệp vụ phức tạp trên một Node duy nhất (Single Node).

Chúng ta không cố gắng tái tạo lại K8s hay Dapr. Thay vào đó, POP tập trung làm cho mỗi Node trở nên **Stateless** và **Idempotent** (Thực thi ngẫu nhiên) để "thân thiện" với các hệ thống phân tán bên ngoài.

### **1.1. Triết lý "Pháo đài Đơn lẻ" (The Robust Fortress)**
Trước khi nghĩ đến việc nhân bản ra 1000 máy, một máy phải chạy **tuyệt đối ổn định**.
*   Nếu Monolith của bạn rò rỉ bộ nhớ, Distributed System của bạn sẽ là thảm họa.
*   Nếu Monolith của bạn không minh bạch, Distributed System của bạn sẽ là hộp đen hỗn loạn.

### **1.2. Khả năng Mở rộng tự nhiên (Nature of Composition)**
POP hỗ trợ mở rộng thông qua tính chất **Hợp nhất (Composability)** của Workflow:
*   Một Workflow lớn có thể được ghép từ nhiều Workflow nhỏ.
*   Một Process có thể gọi một Sub-Workflow.
*   **Chiến lược:** Khi cần mở rộng, ta tách một Sub-Workflow ra khỏi Monolith, đóng gói nó thành một Service riêng, và thay thế lời gọi hàm bằng một Adapter gọi RPC. Code logic nghiệp vụ không thay đổi.

---

# **Chương 16 - An toàn Công nghiệp & Kỷ luật Bất biến (Immutable Governance)**

## 🟥 **1. Vấn đề của "Env Config"**

Trong các framework thông thường, an toàn hệ thống thường là một tùy chọn (Option) có thể bật tắt bằng biến môi trường (`ENABLE_SAFETY=True`). Điều này tạo ra rủi ro chí tử:
*   Môi trường Prod bị config sai -> Thảm họa.
*   Dev tắt check để chạy cho nhanh -> Lỗi lọt xuống Prod.

## 🟦 **2. Giải pháp: Kỷ luật Bất biến (Immutable Governance)**

POP giới thiệu khái niệm **Signed Policy (Chính sách Ký duyệt)**.

### **2.1. Sealed Spec (Đặc tả Đóng băng)**
*   Trong môi trường Production, Engine **từ chối khởi động** nếu không tìm thấy `Manifest.lock` hoặc chữ ký số (Checksum) của Policy không khớp.
*   Các quy tắc an toàn (Safety Rules), giới hạn nhiệt độ, dung sai... được coi là **một phần của Code**, không phải là biến môi trường. Chúng được "bake" (nung cứng) vào Docker Image.

### **2.2. Policy as Code**
*   Spec không được viết trong file `.env` rời rạc.
*   Spec được viết trong các file YAML/JSON versioned, nằm cùng repo với source code (`/specs/v1/safety.yaml`).
*   **CI/CD Pipeline** có trách nhiệm validate spec này và tạo ra chữ ký số trước khi deploy.

**Kết quả:** Runtime không có quyền "nới lỏng" Design time. Dev không thể "lỡ tay" tắt an toàn trên Prod.

---

# **Chương 17 - Runtime Minh bạch (The Transparent Engine)**

## 🟥 **1. Phá bỏ "Hộp đen" (Glass-box Philosophy)**

Một trong những nỗi sợ lớn nhất khi dùng Framework là Engine trở thành "Hộp đen" (Blackbox). Khi có lỗi, Dev không biết do Code mình sai hay do Engine xử lý sai (Scheduling, Locking, Shadowing).

POP cam kết triết lý **"Glass-box" (Hộp kính)**: Engine phải trong suốt như chính Process mà nó thực thi.

## 🟦 **2. Cơ chế Tự giải trình (Self-Explanation)**

Engine bắt buộc phải cài đặt phương thức `explain_decision(tick_id)`.

### **2.1. Decision Trace (Vết quyết định)**
Mỗi nhịp (Tick) của Engine sẽ sinh ra một bản ghi chi tiết:
1.  **Context Snapshot Hash:** Trạng thái đầu vào là gì?
2.  **Selected Process:** Tại sao chọn Process A? (Do điều kiện gì trong Workflow?).
3.  **Skipped Processes:** Tại sao không chọn Process B? (Do thiếu Input? Do Policy chặn?).
4.  **Guard Actions:** Tại sao từ chối ghi vào trường `ctx.x`? (Do vi phạm Contract nào?).

### **2.2. Standard Event Stream**
Engine phát ra một luồng sự kiện chuẩn (Standard Output / Event Bus) để các tool bên ngoài (Dashboard, Log Viewer) có thể visualize dòng chảy của logic.
*   `ENG_START_TICK`
*   `PROC_ACQUIRE_LOCK`
*   `CTX_COMMIT_DELTA`
*   `POLICY_INTERLOCK_TRIGGERED`

## 🟩 **3. Lợi ích**
*   **Auditability:** Khi robot đâm vào tường, ta biết chính xác tại mili-giây đó Engine đang nghĩ gì, tại sao nó không dừng lại.
*   **Trust:** Dev tin tưởng hệ thống vì họ nhìn thấy "bánh răng" đang quay bên trong.

---

# **Chương 18 - Chiến lược Kiểm thử (Testing Strategy)**

*(Giữ nguyên nội dung về Testing Pyramid nhưng nhấn mạnh vào việc test các Policy và Governance)*

### **Test Level 5: Governance Test**
*   Ngoài Unit/Integration Test, ta thêm tầng test Policy.
*   CI/CD chạy test để đảm bảo: "Nếu tôi chỉnh nhiệt độ > 100, hệ thống CÓ thực sự kích hoạt E-STOP không?".
*   Đây là tầng test bắt buộc để sinh ra `Signed Policy`.

---

## 🏁 **LỜI KẾT**

Với lần tái định vị này, POP SDK quay trở lại với sứ mệnh cốt lõi: Làm chỗ dựa vững chắc cho những hệ thống nghiệp vụ phức tạp nhất. Chúng ta không lan man đi giải quyết bài toán của Cloud, chúng ta giải quyết bài toán của **Sự phức tạp (Complexity)** và **Độ tin cậy (Reliability)**.

**Robust First. Scale Later.**
