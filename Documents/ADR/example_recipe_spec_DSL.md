Dưới đây là cấu trúc YAML mẫu (Recipe Spec) để định nghĩa các quy tắc kiểm soát phạm vi (Range/Tolerance) cho Context.

Quy tắc này được Engine Gatekeeper (lý tưởng là bằng Rust để đạt hiệu năng Zero-cost) sử dụng để kiểm tra mọi dữ liệu được ghi vào Context trước khi Commit, nhằm đạt được tính an toàn công nghiệp.

### Ví dụ Cấu trúc Recipe Spec (YAML)

```yaml
recipe_spec:
  version: "1.0"
  description: "Quy tắc kiểm soát cho quy trình Robot nung chảy (Fusion Process)"

# 1. GLOBAL CONTEXT (ECM - Equipment Constants)
#   Áp dụng Zero Tolerance. Vi phạm => Dừng khẩn cấp (Interlock)
global_specs:
  System.Mode:
    type: string
    fixed_value: "PRODUCTION"
    on_violation: INTERLOCK #

# 2. DOMAIN CONTEXT (FDC - Fault Detection & Classification)
#   Áp dụng kiểm soát Range Spec và chính sách đa cấp độ.
domain_specs:
  fusion_temperature:
    type: float
    unit: Celsius
    range: [180.0, 220.0]
    # Chính sách đa cấp độ
    tolerance_low: 5.0 # (Nếu 175-180)
    tolerance_high: 10.0 # (Nếu 220-230)
    on_tolerance_violation: WARNING # Ghi log nếu vượt ngưỡng nhẹ
    on_range_violation: INTERLOCK # Dừng nếu vượt ngưỡng nghiêm trọng (ví dụ: < 175 hoặc > 230)

  pressure_psi:
    type: int
    range:
    on_range_violation: ALARM

# 3. LOCAL CONTEXT (RMS - Process Parameters)
#   Kiểm soát biến tạm thời chỉ trong phạm vi Process, giúp cô lập lỗi.
local_specs:
  intermediate_score:
    type: float
    range: [0.0, 1.0]
    on_range_violation: FAILFAST # Process tự hủy nếu tính toán sai

# 4. SIDE EFFECT CONTROL (Adapter/I/O)
side_effect_specs:
  database.write_log:
    rate_limit: 10 # Cho phép ghi tối đa 10 lần/giây
    whitelist_paths: ["/var/log/pop"]
```

**Phân tích ngắn gọn:**

*   Mô hình này cho phép thay đổi ngưỡng nhiệt độ (từ 220.0 thành 250.0) bằng cách sửa file YAML và tải lại Spec (Policy Hot-swap) mà **không cần thay đổi hoặc biên dịch lại Process code**.
*   ContextGuard sẽ dùng các quy tắc này để chặn dữ liệu ghi vào Context (commit) nếu chúng vi phạm mức độ **INTERLOCK**.

