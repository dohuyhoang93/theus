# Bước 6: Ra Trận (Production Readiness)

---

## 6.1. Từ Phòng Thí Nghiệm ra Nhà Máy

Code chạy ngon trên máy dev không có nghĩa là nó sống sót được ở Production.
Theus cung cấp 2 vũ khí để bảo vệ hệ thống của bạn:
1.  **Integrity Audit:** Đảm bảo dữ liệu không bị sai lệch.
2.  **Telemetry:** Biết chính xác chuyện gì đang xảy ra.

---

## 6.2. Hệ thống Kiểm Toán (Audit System)

Bạn đã khai báo Contract (`inputs`/`outputs`) trong Process. Nhưng ai đảm bảo Contract đó được thực thi đúng?
Ví dụ: Process hứa trả về `score` dương, nhưng bug logic lại tính ra `-1`.

### Audit Recipe (`specs/audit_recipe.yaml`) - Tùy Chọn
Đây là nơi bạn định nghĩa "Luật chơi" cho toàn bộ hệ thống. Theus Framework sử dụng cơ chế này để "cưỡng chế" sự trong sạch của dữ liệu.

> **Lưu ý:** Audit là **TÙY CHỌN (Optional)**. Nếu bạn không cung cấp file recipe, hệ thống sẽ chạy ở chế độ "Unchecked Mode" (bỏ qua bước kiểm tra Input/Output).

```yaml
version: "2.1"
recipes:
  # Luật cho process 'check_image_quality'
  domain.vision.check_quality:
    outputs:
      - target: "domain.vision.brightness"
        condition: "min"
        value: 0
        level: "B" # Block: Rollback transaction nếu vi phạm
        max_threshold: 3 # Cho phép sai 2 lần, lần 3 mới chặn
```

### Các Cấp độ Vi phạm (Violation Levels - v2.1)
*   **Level A (Abort - Trước đây là S):** Dừng ngay lập tức (Crash). Dùng cho vi phạm an toàn.
*   **Level B (Block):** Chặn Transaction (Rollback), nhưng không crash app. Dùng cho lỗi nghiệp vụ.
*   **Level C (Campaign - Trước đây là W):** Chỉ ghi log cảnh báo và tiếp tục.

### Cơ chế Thông minh (Smart Features)
1.  **Dual Thresholds:** Kích hoạt cảnh báo sớm tại `min_threshold` và chặn tại `max_threshold`.
2.  **Cyclic Reset:** Khi chạm ngưỡng `max_threshold`, hệ thống thực thi hành động (Block/Log) và tự động Reset bộ đếm về 0.
3.  **Smart Conditions:** Hỗ trợ `max_len`, `min_len` để kiểm tra độ dài List/String mà không cần code thêm.
    ```yaml
    - field: "domain.queue"
      condition: "max_len"
      value: 100
    ```

---

## 6.3. Theus CLI Audit

Trước khi deploy, hãy chạy lệnh audit để scan toàn bộ mã nguồn:

```bash
# 1. Tạo file recipe mẫu từ code hiện tại
theus audit gen-spec > specs/audit_recipe.yaml

# 2. Kiểm tra code có tuân thủ recipe không
theus audit verify
```

Nếu bạn lỡ tay xóa một field trong `outputs` của process nhưng quên cập nhật `audit_recipe.yaml`, lệnh `verify` sẽ báo lỗi ngay. **Không bao giờ deploy code lệch chuẩn ra production.**

---

## 6.4. Deployment (Docker)

Theus được thiết kế để "Cloud Native". Một Theus Node đóng gói gọn trong 1 Docker container.

### `Dockerfile` chuẩn:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 1. Cài dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2. Copy source
COPY src/ ./src/
COPY adapters/ ./adapters/
COPY specs/ ./specs/

# 3. Chạy
CMD ["theus", "run", "specs/workflow.yaml", "--mode", "production"]
```

---

## 6.5. Lời kết: Bạn đã tốt nghiệp!

Chúc mừng bạn! Bạn đã đi từ con số 0 đến một hệ thống Theus hoàn chỉnh:
1.  **Context:** Dữ liệu có cấu trúc (3 Trục).
2.  **Process:** Logic thuần túy, an toàn.
3.  **Workflow:** Dòng chảy rõ ràng.
4.  **Adapter:** Cách ly thế giới bên ngoài.
5.  **Audit:** Lưới an toàn cuối cùng.

Giờ là lúc bạn dùng Theus để xây dựng những hệ thống mạnh mẽ, tin cậy và "không thể chết".

**Happy Coding with Theus!**
