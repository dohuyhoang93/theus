# Đề cương: Sổ tay Đồng hành POP (The POP Companion Handbook)

---

## 🟥 Triết lý Tiếp cận (The Approach)

Khác với phần "Lý thuyết Cốt lõi" (Core Specification) khô khan và nghiêm ngặt, cuốn Sổ tay này được thiết kế như một người bạn đồng hành (Mentor).
*   **Phong cách:** Tiến hóa (Evolutionary). Không áp đặt toàn bộ kiến trúc ngay từ đầu.
*   **Phương pháp:** Đặt vấn đề (Tại sao code hiện tại khó bảo trì?) -> Gợi mở giải pháp (Tư duy POP) -> Thực hành (Dùng `pop-sdk`).
*   **Mục tiêu:** Giúp Developer tự nhận ra giá trị của POP qua từng bài toán cụ thể.

---

## 🟦 Lộ trình Tiến hóa (The Evolutionary Arc)

### **Bước 1: Từ Hỗn loạn đến Ngăn nắp (Taming the Data)**
*   **Vấn đề:** "Tôi không biết ai đang sửa dữ liệu của tôi."
*   **Giải pháp Tư duy:** Config as Code. Single Source of Truth.
*   **Thực hành SDK:**
    *   Định nghĩa `context_schema.yaml`.
    *   Tự động load vào `dataclasses`.

### **Bước 2: Nghệ thuật của Hành động Thuần khiết (The Art of Pure Action)**
*   **Vấn đề:** "Hàm này vừa tính toán, vừa ghi log, vừa gọi DB."
*   **Giải pháp Tư duy:** Tách biệt Logic (Process) và An toàn (Audit).
*   **Thực hành SDK:**
    *   Viết hàm `@process` với Contract.
    *   Hiểu về "Dual Layer Protection" (Code Logic vs. Audit Rules).

### **Bước 3: Dòng chảy Tuyến tính (The Linear Flow)**
*   **Vấn đề:** "Spaghetti Code gọi hàm chằng chịt."
*   **Giải pháp Tư duy:** Linear Pipeline. Ưu tiên sự ổn định.
*   **Thực hành SDK:**
    *   Định nghĩa `workflow.yaml`.
    *   Hiểu tại sao V2 lại giới hạn ở Linear (Robustness).

### **Bước 4: Tương tác với Thực tại (Interacting with Reality)**
*   **Vấn đề:** "Làm sao test logic mà không cần DB thật?"
*   **Giải pháp Tư duy:** Adapter Pattern.
*   **Thực hành SDK:**
    *   Inject Adapter vào Context.

### **Bước 5: [Tạm ẩn trong V2 MVP] Chinh phục Đại Monolith**
*   *Lưu ý: Các tính năng nâng cao (Branching, Loop) sẽ được giới thiệu trong V2.x.*

### **Bước 6: Sẵn sàng ra Trận (Production Readiness)**
*   **Vấn đề:** "Làm sao đảm bảo an toàn tuyệt đối cho giao dịch?"
*   **Giải pháp Tư duy:** Industrial Audit System (RMS/FDC).
*   **Thực hành SDK:**
    *   Định nghĩa `audit_recipe.yaml` (S/A/B/C).
    *   Sử dụng CLI `pop audit` để generate và inspect luật.

---

## 🟩 Định dạng Trình bày

Mỗi chương sẽ tuân theo cấu trúc:
1.  **Chuyện nhà Dev:** Một tình huống đau đầu thực tế (e.g., "Bug lúc 3 giờ sáng").
2.  **Câu hỏi Gợi mở:** "Tại sao chúng ta lại để dữ liệu chạy lung tung như vậy?"
3.  **Góc nhìn POP:** Giới thiệu khái niệm giải quyết vấn đề.
4.  **Show me the Code:** Hướng dẫn từng bước với `pop-sdk`.
5.  **Challenge:** Bài tập nhỏ để Dev tự mở rộng.
