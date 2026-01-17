# ADR: Ngữ nghĩa & Vòng đời của Local Context (Persistence vs Ephemeral)

**Trạng thái:** Xác nhận (Confirmed Behavior cho v2.1)
**Ngày:** 22/12/2025
**Tác giả:** Theus AI & User

## 1. Vấn đề
Trong kiến trúc 3 Trục (Layer/Semantic/Zone), trục **Layer** định nghĩa phạm vi sống (Global, Domain, Local).
Về mặt ngữ nghĩa thông thường, **Local** thường được hiểu là "cục bộ hàm" (Function scope / Stack scope) - tức là sinh ra khi Process bắt đầu và hủy khi Process kết thúc.

Tuy nhiên, trong triển khai thực tế của `TheusEngine` v2.1:
*   `SystemContext` là một đối tượng tồn tại xuyên suốt vòng đời Engine.
*   Nếu `Local Context` được định nghĩa là một trường con của `SystemContext`, nó sẽ **tồn tại vĩnh viễn** cùng với object cha.

Câu hỏi: Liệu Process B có nhìn thấy dữ liệu "Local" do Process A ghi đè trước đó không? Và điều này có vi phạm nguyên tắc thiết kế không?

## 2. Phân tích Hiện trạng (v2.1)

### Cơ chế hoạt động:
*   Engine chuyển cùng một tham chiếu `ctx` (SystemContext) cho chuỗi các Process: `A(ctx) -> B(ctx) -> C(ctx)`.
*   Engine **KHÔNG** thực hiện bất kỳ hành động "Reset/Clear" nào đối với `ctx.local` giữa các bước chuyển.

### Hệ quả:
1.  **Shared Visibility:** Process B hoàn toàn có thể đọc được biến `ctx.local.temp_x` mà Process A vừa ghi.
2.  **Dirty Read Risk:** Nếu Process B mong đợi `ctx.local` sạch sẽ, nó có thể gặp lỗi nếu Process A để lại "rác".
3.  **Short-term Memory (Tính năng ẩn):** Developer có thể lợi dụng đặc điểm này để truyền dữ liệu tạm (Transient Data) giữa A và B mà không muốn làm ô nhiễm Domain chính (Persistent Domain).

## 3. Quyết định (Decision)

Chúng ta chấp nhận hành vi hiện tại trong v2.1 và định nghĩa lại ngữ nghĩa của **Local** như sau:

> **Trong Theus v2.1, "Local Context" là "Chain-Scoped Context" (Bộ nhớ ngắn hạn của Chuỗi), KHÔNG PHẢI "Frame-Scoped Context" (Bộ nhớ ngăn xếp).**

Nó đóng vai trò là vùng đệm trung gian (Scratchpad) cho một Workflow instance.

## 4. Hướng dẫn Sử dụng (Guidelines)

### Nên làm (Do):
*   Sử dụng `ctx.local` để truyền dữ liệu tạm giữa 2 bước liên tiếp (ví dụ: `Calculate -> Format`).
*   Tự chủ động clear các trường quan trọng nếu sợ rủi ro bảo mật/logic.

### Không nên làm (Don't):
*   Giả định `ctx.local` luôn trống khi bắt đầu Process.
*   Lưu trữ state cần bền vững (Persistent) vào Local (hãy dùng Domain).

## 5. Lộ trình (Roadmap v2.2)

Để hỗ trợ những người theo chủ nghĩa thuần túy (Purists), v2.2 sẽ giới thiệu cờ cấu hình:

```python
# Tự động reset local context sau mỗi bước
engine = TheusEngine(ctx, auto_reset_local=True)
```

Hoặc hỗ trợ Hook `on_process_end` để dọn dẹp. Nhưng mặc định (Default) vẫn sẽ giữ hành vi Persistence để đảm bảo Performance và Backward Compatibility.
