# Chương 1: Theus v2 - Kỷ nguyên của Lập trình Hướng Quy trình (POP)

## 1. Triết lý của Theus: "Zero Trust" State Management
Trong phát triển phần mềm hiện đại (AI Agents, Automation, Banking), vấn đề lớn nhất là sự hỗn loạn của trạng thái (State). Dữ liệu bị biến đổi không kiểm soát, sự kiện (Event) bị trộn lẫn với dữ liệu bền vững (Data), dẫn đến những con bug không thể tái hiện (Non-deterministic bugs).

**Theus v2** không chỉ là một thư viện, nó là một **Hệ điều hành thu nhỏ** cho quy trình của bạn, ép buộc bạn tuân thủ mô hình **Context 3 Trục (3-Axis Context Model)**:
1.  **Layer:** Dữ liệu sống ở đâu? (Global/Domain/Local).
2.  **Semantic:** Dữ liệu dùng để làm gì? (Input/Output).
3.  **Zone:** Dữ liệu được bảo vệ thế nào? (Data/Signal/Meta).

## 2. Tại sao lại là POP v2?
Các mô hình cũ (OOP, FP) đều thiếu một mảnh ghép: **Sự kiểm soát Kiến trúc tại Runtime.**
- **OOP:** Đóng gói tốt, nhưng luồng dữ liệu (Data Flow) bị ẩn trong các phương thức.
- **Theus POP:** Tách biệt hoàn toàn:
    - **Context:** Là kho dữ liệu "tĩnh", được chia vùng (Zoning) nghiêm ngặt.
    - **Process:** Là các hàm "vô tri" (stateless), chỉ được phép chạm vào Context thông qua **Hợp đồng (Contract)**.

## 3. Các thành phần chính của Theus v2
1.  **TheusEngine:** Bộ não điều phối, tích hợp sẵn Transaction Manager và Lock Manager.
2.  **Hybrid Context:** Hệ thống lưu trữ thông minh, tự động phân loại Data (Bền vững) và Signal (Thoáng qua).
3.  **Audit System:** Cảnh sát giao thông, chặn đứng các giao dịch vi phạm quy tắc nghiệp vụ (Rule-based Enforcement).
4.  **Workflow FSM:** Nhạc trưởng điều phối luồng đi dựa trên sự kiện.

## 4. Cài đặt
Theus v2 yêu cầu Python 3.12+ và tuân thủ các chuẩn Typing hiện đại.

```bash
# Cài đặt từ source
pip install -e .
```

---
**Bài tập Chương 1:**
Hãy quên đi cách code cũ. Hãy tưởng tượng hệ thống của bạn là một nhà máy.
- Đâu là nguyên liệu (Input)?
- Đâu là sản phẩm (Output)?
- Đâu là còi báo động (Signal)?
Trong Chương 2, chúng ta sẽ xây dựng "nhà kho" (Context) cho nhà máy này.