# Chương 9: Severity Levels - Tháp Hình Phạt

Trong Theus v2, Level không chỉ là cái nhãn log. Nó định nghĩa chính xác **HÀNH ĐỘNG** mà Engine sẽ thực thi.

## 1. Bảng phân cấp hành động

| Level | Tên gọi | Exception (Lỗi) | Hành động của Engine | Ý nghĩa |
| :--- | :--- | :--- | :--- | :--- |
| **S** | **Safety Interlock** | `AuditInterlockError` | **Emergency Stop** | Dừng toàn bộ hệ thống/Workflow. Không cho chạy tiếp bất cứ cái gì. Dùng cho lỗi an toàn. |
| **A** | **Abort** | `AuditInterlockError` | **Hard Stop** | Giống S về mặt code, nhưng ngữ nghĩa là "Lỗi Logic nghiêm trọng". Dừng Workflow. |
| **B** | **Block** | `AuditBlockError` | **Rollback** | Chỉ từ chối Process này. Transaction bị hủy. Workflow **VẪN SỐNG** và có thể thử lại hoặc đi nhánh khác. |
| **C** | **Campaign** | (None) | **Log Warning** | Chỉ ghi log vàng. Process vẫn Commit thành công. |
| **I** | **Ignore** | (None) | **Silent** | Không làm gì cả. |

## 2. Khi nào dùng cái gì?
- Dùng **S** cho giới hạn vật lý (Nhiệt độ, Áp suất, Max Memory).
- Dùng **A** cho lỗi dữ liệu không thể phục hồi (Mất kết nối DB chính, Dữ liệu rác).
- Dùng **B** cho lỗi nghiệp vụ thông thường (Sai format, Hết hạn mức, Trùng tên).
- Dùng **C** cho KPI (Thời gian chạy hơi lâu, Giá trị hơi cao nhưng chấp nhận được).

## 3. Catching Errors
Trong code điều khiển (Orchestrator):
```python
try:
    engine.run_process("add_product", ...)
except AuditBlockError:
    print("Bị chặn nhẹ, thử lại sau...")
except AuditInterlockError:
    print("DỪNG NGAY LẬP TỨC! GỌI CỨU HỎA!")
    sys.exit(1)
```

---
**Thực hành:**
Thử cấu hình Audit Level `S`. Vi phạm nó và quan sát exception `AuditInterlockError`. Thử cấu hình `B` và quan sát `AuditBlockError`. Viết code `try/except` để xử lý 2 trường hợp này khác nhau.