# Bước 6: Sẵn sàng ra Trận (Production Readiness) "Industrial Grade"

---

## 6.1. Từ "Đồ chơi" lên "Công nghiệp"

Bạn đã có Code chạy ngon (Step 2), Luồng chạy mượt (Step 3). Nhưng để **Ra Trận (Production)**, hệ thống cần nhiều hơn thế. Nó cần khả năng **"Tự vệ"**.

Trong môi trường Công nghiệp (như Nhà máy, Hàng không, hay Fintech), chúng ta không chỉ quan tâm "Chạy đúng", mà còn phải đảm bảo "Không được chạy sai mức nguy hiểm".

POP V2 giới thiệu **Hệ thống Kiểm toán Công nghiệp (Industrial Audit System)** lấy cảm hứng từ chuẩn FDC (Fault Detection & Classification) và RMS (Recipe Management System).

---

## 6.2. Hai Cổng Kiểm Soát (The Two Gates)

Mỗi Process trong POP V2 giờ đây được bảo vệ bởi 2 cánh cổng:

1.  **Cổng Vào (Input Gate - RMS Check):**
    *   Trước khi Process chạy, hệ thống kiểm tra nguyên liệu đầu vào (Context).
    *   Ví dụ: "Tuổi user phải >= 18". Nếu sai -> CHẶN NGAY.
2.  **Cổng Ra (Output Gate - FDC Check):**
    *   Sau khi Process chạy xong (nhưng trước khi trả kết quả cho User), hệ thống kiểm tra thành phẩm.
    *   Ví dụ: "Số tiền chuyển đi không được âm". Nếu sai -> BÁO ĐỘNG hoặc DỪNG.

Tất cả được cấu hình trong `audit_recipe.yaml`. Code logic của bạn **không cần biết** về việc này (Separation of Concerns).

---

## 6.3. 4 Cấp độ Nghiêm trọng (S/A/B/C)

Khi có lỗi vi phạm, hệ thống sẽ xử lý theo 4 cấp độ chuẩn công nghiệp:

*   **S (Stop/Stick - Nghiêm trọng):**
    *   **Hành động:** Dừng ngay lập tức (Interlock). Rollback transaction.
    *   **Dùng cho:** Lỗi an toàn, lỗi dữ liệu không thể phục hồi.
    *   *Ví dụ: Chuyển tiền tài khoản âm.*

*   **A (Abort/Warning - Ngưỡng):**
    *   **Hành động:** Cảnh báo trước. Nếu vi phạm quá N lần liên tiếp -> Dừng (Interlock).
    *   **Dùng cho:** Lỗi hiệu năng, lỗi tài nguyên (Retries).
    *   *Ví dụ: Gọi API timeout quá 3 lần.*

*   **B (Block/Hold - Nghiệp vụ):** 
    *   **Ý nghĩa:** Lỗi logic kinh doanh (Business Logic) hoặc dữ liệu bất thường. Code không sai, nhưng cần con người kiểm duyệt.
    *   **Hành động:** Chặn quy trình (giống S/Interlock trong bản Linear) nhưng đánh dấu là "Block" để đội vận hành (Operator) xử lý thủ công.
    *   *Ví dụ: Nghi ngờ gian lận (Fraud check), Giao dịch quá lớn.*

*   **C (Continue/Log - Thông tin):**
    *   **Hành động:** Chỉ ghi Log và chạy tiếp. 
    *   **Cơ chế Throttling:** Để tránh làm ngập log, hệ thống chỉ ghi cảnh báo ở lần thứ 1, 10, 100...
    *   *Ví dụ: User login giờ lạ.*

*   **I (Ignore/Bypass - Bỏ qua):**
    *   **Hành động:** Không kiểm tra, không log (No-op).
    *   **Dùng cho:** Khai báo các object phức tạp (Tensor, Adapter) để giữ tính minh bạch trong file config nhưng tránh lỗi runtime khi so sánh.
    *   *Ví dụ: `env.camera_adapter`.*

---

## 6.3b. Chiến lược Bypass & Chống Spam (Hardening Guide)

Trong thực tế vận hành (như AI Vision 60fps), bạn sẽ gặp các đối tượng phức tạp (Tensor, Adapter) hoặc nguy cơ ngập tràn log. Đây là giải pháp:

### 1. Xử lý Complex Objects (Tensor, Adapter)
Nếu `audit_recipe` cố gắng so sánh giá trị (`min`, `max`) của một Tensor lớn, hệ thống sẽ lỗi.
*   **Giải pháp 1 (An toàn):** Dùng `condition: exists` và `level: S`. Chỉ kiểm tra nó không phải `None`.
*   **Giải pháp 2 (Bypass Tường minh - Khuyên dùng):** Dùng Level `I`.
    ```yaml
    - target: env.camera_adapter
      level: I # Ignore: Khai báo để biết là có dùng, nhưng Engine sẽ bỏ qua.
    ```

### 2. Chống Spam Log (Log Throttling)
Nếu Level `C` (Info) được kích hoạt liên tục trong vòng lặp model AI (60 lần/giây), file log sẽ bị rác.
*   **Cơ chế:** POP Engine tự động kích hoạt **Throttling**.
*   **Hoạt động:** Chỉ log cảnh báo ở lần vi phạm thứ **1, 10, 100, 1000...**
*   Các vi phạm trung gian sẽ được đếm ngầm (Counter) nhưng **không in ra màn hình**.

### 3. Quy tắc "Tường minh" (Transparency Rule)
Đừng xóa ngầm (Implicit Remove) các field khỏi `audit_recipe.yaml` nếu bạn vẫn dùng nó. Hãy khai báo nó với Level `I`. Điều này giúp người khác đọc file config hiểu được toàn bộ inputs/outputs của hệ thống.

---

## 6.4. Cách dùng: CLI `pop audit`

Bạn không cần viết file YAML bằng tay từ đầu. POP SDK cung cấp công cụ tự động.

### 1. Tạo Spec tự động (`gen-spec`)
SDK sẽ quét code `@process` của bạn và tạo bộ khung Audit:

```bash
pop audit gen-spec
```

Kết quả (`specs/audit_recipe.yaml`):

```yaml
process_recipes:
  validate_order:
    input_rules:
      - target: domain_ctx.order.amount
        condition: min
        value: 0
        level: S
    output_rules:
      - target: domain_ctx.inventory.stock
        condition: min
        value: 0
        level: A
        threshold: 3
```

### 2. Kiểm tra Rules (`inspect`)
Để xem Process `validate_order` đang chịu những luật nào:

```bash
pop audit inspect validate_order
```

---

## 6.5. Unit Test với Audit

Kiểm thử bây giờ không chỉ là logic đúng, mà là **Luật có được thực thi không**.

```python
def test_audit_violation(self):
    # Setup Context với dữ liệu sai
    ctx.domain_ctx.order.amount = -50
    
    # Engine tự động kích hoạt Audit Check
    with self.assertRaises(AuditInterlockError) as cm:
        engine.run_process("validate_order")
    
    print("✅ Hệ thống đã chặn giao dịch âm tiền thành công!")
```

---

## 6.6. Lời kết: Bạn đã là một Kỹ sư POP (POP Engineer)

Chúc mừng! Bạn đã đi hết hành trình để trở thành một Kỹ sư POP thực thụ.

1.  **Data:** Bạn biết dùng `ContextSchema`.
2.  **Process:** Bạn viết hàm thuần khiết `Pure Function`.
3.  **Config:** Bạn quản lý bằng `Recipe` và `Workflow`.
4.  **Audit:** Bạn bảo vệ hệ thống bằng `S/A/B/C`.

Hệ thống của bạn giờ đây không chỉ "Chạy được", mà còn "Kiên cố" (Robust), "Minh bạch" (Transparent) và "Dễ mở rộng" (Scalable).

**Hãy để Code của bạn ngủ ngon, vì POP Audit đang canh gác cho bạn!**
