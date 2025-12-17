# Bước 5: Tổ hợp Phức tạp (The Complex Monolith)

---

## 5.1. Chuyện nhà Dev: "Bản vẽ dài 10 mét"

Dự án của bạn thành công. File `checkout_flow.yaml` từ 5 bước giờ đã dài 50 bước.
*   "Nếu user là VIP thì chạy 5 bước A".
*   "Nếu user mua hàng quốc tế thì chạy 10 bước B".

Nhưng Engine hiện tại chỉ chạy **Tuyến tính (Linear)**. Bạn không thể viết `if/else` trong YAML. Khủng hoảng xảy ra.

---

## 5.2. Sự thật về SDK (V1): Giới hạn Đệ quy

Bạn có thể nghĩ: *"Tại sao không cho Process gọi lại Engine? (Đệ quy)"*
Tôi đã thử nghiệm kỹ lưỡng điều này và kết luận: **KHÔNG NÊN LÀM VẬY TRONG PHIÊN BẢN HIỆN TẠI.**

*   **Tại sao:** Hệ thống Transaction và Lock của SDK V1 chưa hỗ trợ "Lồng nhau" (Nested Transactions). Việc gọi Engine bên trong Engine dễ dẫn đến **Deadlock** (Treo) hoặc xung đột dữ liệu.
*   **Roadmap:** Tính năng "Sub-Workflow" chính thức sẽ có trong phiên bản V2.

Vậy giải pháp hiện tại là gì? **Signal Pattern (Mẫu Tín hiệu).**

---

## 5.3. Giải pháp: Signal Pattern (Người điều phối nằm ở Main)

Thay vì Process tự quyết định và gọi Engine (rất nguy hiểm), Process chỉ cần **Ra Tín hiệu**.
Logic điều hướng sẽ nằm ở lớp ngoài cùng (`main.py`).

### **Bước A: Process trả về Tín hiệu**
Viết một Process đóng vai trò "Bộ định tuyến" (Router). Nhiệm vụ duy nhất là check điều kiện và trả về tên quy trình tiếp theo.

```python
@process(
    name="route_checkout",
    inputs=['domain.user.rank'],
    outputs=[],
    errors=[] 
)
def route_checkout(ctx: SystemContext):
    rank = ctx.domain.user.rank
    
    if rank == "VIP":
        # Trả về một chuỗi đặc biệt để báo hiệu
        return "SIGNAL:RUN_VIP"
    else:
        return "SIGNAL:RUN_STANDARD"
```

### **Bước B: Tổ chức Workflow**
Chúng ta chia nhỏ các file YAML:
1.  `workflows/setup.yaml`: Chạy các bước chuẩn bị, cuối cùng là `route_checkout`.
2.  `workflows/vip.yaml`: Quy trình VIP.
3.  `workflows/standard.yaml`: Quy trình thường.

### **Bước C: "Bộ não" tại `main.py`**
Chúng ta viết một vòng lặp nhỏ trong `main.py` để hứng tín hiệu.

```python
# main.py

# Bắt đầu với bước Setup
current_flow = "workflows/setup.yaml"

while current_flow:
    print(f"--- Running Flow: {current_flow} ---")
    
    # 1. Chạy workflow hiện tại
    # Lưu ý: Engine cần cập nhật hàm run để trả về kết quả của bước cuối cùng
    # Hoặc chúng ta kiểm tra trạng thái trong Context
    engine.execute_workflow(current_flow)
    
    # 2. Kiểm tra tín hiệu từ Context (Cách an toàn nhất)
    # Giả sử chúng ta quy ước lưu tín hiệu vào domain.system_signal
    signal = ctx.domain.system_signal
    
    # 3. Điều hướng (Routing Logic)
    if signal == "SIGNAL:RUN_VIP":
        current_flow = "workflows/vip.yaml"
        ctx.domain.system_signal = "" # Reset signal
    elif signal == "SIGNAL:RUN_STANDARD":
        current_flow = "workflows/standard.yaml"
        ctx.domain.system_signal = ""
    else:
        # Không có tín hiệu -> Kết thúc
        current_flow = None
```

---

## 5.4. Quyền lực & Trách nhiệm

Cách tiếp cận này hơi thủ công (bạn phải viết code if/else ở main), nhưng nó mang lại sự **An toàn Tuyệt đối**.
*   **Không Deadlock:** Mỗi Workflow chạy xong, Commit transaction, thoát ra, rồi mới chạy Workflow kia. Không có Transaction lồng nhau.
*   **Minh bạch:** Nhìn vào `main.py` là thấy ngay sơ đồ điều hướng tổng thể.

> **Ghi chú về Tương lai (Roadmap):**
> Team phát triển SDK đang làm việc trên tính năng `Native Branching` trong YAML (ví dụ: `next: vip_flow if $domain.is_vip`). Khi đó, bạn có thể xóa đoạn code điều hướng trong `main.py` đi. Nhưng hiện tại, Signal Pattern là giải pháp "Best Practice".

---

## 5.5. Tổng kết Bước 5

*   **Hiện tại (V1):** Tránh gọi Engine đệ quy. Dùng Signal Pattern.
*   **Chia nhỏ:** Giữ các file YAML nhỏ gọn, chuyên biệt.
*   **Main Loop:** Biến `main.py` thành một "State Machine" đơn giản để nối các file YAML lại với nhau.

**Thử thách:** Hãy áp dụng Signal Pattern để xử lý nút "Retry". Nếu thanh toán lỗi, Process trả về `SIGNAL:RETRY`. Main loop sẽ đếm số lần thử, nếu < 3 thì chạy lại dòng `payment_flow.yaml`.
