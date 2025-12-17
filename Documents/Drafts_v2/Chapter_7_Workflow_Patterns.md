# Chương 7: Mô hình Workflow & Ngôn ngữ DSL

---

## 7.1. Workflow là một Đồ thị (Graph Theory applied)

Trong POP, Workflow không phải là danh sách việc cần làm (ToDo List), mà là một **Đồ thị Thực thi (Execution Graph)**.
Mỗi nút (Node) là một Process. Các cạnh (Edge) là dòng chảy dữ liệu.

Tuy nhiên, POP V2 (Giai đoạn "The Robust Node") ưu tiên sự **Ổn định** hơn sự Phức tạp.
Vì vậy, Engine hiện tại hỗ trợ chính thức mô hình **Linear** (Tuyến tính). Các mô hình phức tạp khác được xếp vào lộ trình tương lai (V2.x).

---

## 7.2. Các Mô hình Workflow

### A. Linear (Tuyến tính) - HỖ TRỢ CHÍNH THỨC
*   **Mô hình:** `Nodes` được nối tiếp nhau thành chuỗi đơn `P1 → P2 → P3`.
*   **Chi tiết:** Đây là dạng cơ bản nhất, đảm bảo thứ tự thực thi tuyệt đối.
*   **DSL Example (`workflows/main_workflow.yaml`):**
    ```yaml
    name: "Standard Checkout Flow"
    steps:
      - validate_order            # String notation (Simple)
      - process: check_inventory  # Dict notation (Advanced)
        timeout: 5s               # (Future feature)
      - payment_processing
      - shipping_label
    ```

### B. Branching (Rẽ nhánh) - ROADMAP V2.1
*   **Mô hình:** `P1 → if (State) { P2a } else { P2b }`.
*   **Hiện tại:** Để rẽ nhánh trong V2 MVP, bạn hãy xử lý logic điều hướng bên trong Process, hoặc dùng Python script điều phối `POPEngine`.
*   **DSL Dự kiến:**
    ```yaml
    steps:
      - branch:
          when: "ctx.quality_score > 0.9"
          then: [fast_track]
          else: [manual_review]
    ```

### C. DAG (Song song hóa) - ROADMAP V2.2
*   **Mô hình:** `P1 → {P2, P3} → P4`.
*   **Challenge:** Xử lý Merge State rất phức tạp nếu không có Lock Manager tốt.
*   **Hiện tại:** Chưa hỗ trợ. Hãy chạy tuần tự.

### D. Dynamic (Vòng lặp) - ROADMAP V2.3
*   **Mô hình:** `P1 → P2 → P1`.
*   **Hiện tại:** Chưa hỗ trợ.

---

## 7.3. Tại sao chỉ Linear?

Bạn có thể thất vọng: *"Tại sao Engine lại yếu thế?"*

Câu trả lời: **Robustness (Sự bền vững).**
1.  **Dễ Debug:** Linear flow cực kỳ dễ trace lỗi. Nếu P2 lỗi, chắc chắn P1 đã xong.
2.  **Dữ liệu an toàn:** Không có Race Condition (điều ám ảnh nhất của Parallel).
3.  **Thay thế được:** Nếu cần logic quá phức tạp (Nested Loop, State Machine), bạn hoàn toàn có thể viết một Process Python thuần túy để điều phối (Orchestrator Pattern).

> **Triết lý POP:** Workflow YAML chỉ nên làm xương sống. Đừng cố biến YAML thành ngôn ngữ lập trình Turing-complete.

---

## 7.4. Trách nhiệm của Engine (Engine Responsibilities)

1.  **Graph Validation:** (Future) Kiểm tra cấu trúc flow.
2.  **Snapshot & Rollback:** (Đã có trong V2) Mỗi Process chạy trong Transaction. Lỗi tự rollback.
3.  **Audit Trace:** (Đã có trong V2) Ghi lại nhật ký Audit (S/A/B/C).
