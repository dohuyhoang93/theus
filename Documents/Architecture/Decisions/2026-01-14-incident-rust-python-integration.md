# Phân Tích Sự Cố Tích Hợp Rust-Python: Slice Mutation & ContextGuard

**Ngày:** 2026-01-14
**Người thực hiện:** Antigravity (AI Assistant)
**Dựa trên:** Bộ quy tắc Tư duy Phản biện (Critical Thinking Rules)

## 1. Vấn đề (Problem)
*   **Vấn đề cốt lõi:** Một thay đổi nhỏ nhằm sửa lỗi `Slice Mutation` trong `TrackedList` đã gây ra hiệu ứng domino ("cascade failure"), làm lộ ra hàng loạt lỗi tiềm ẩn trong kiến trúc cầu nối Rust-Python (PyO3).
*   **Cụ thể:**
    1.  Rebuild extension làm lộ ra cấu hình module thiếu sót (`builtins.ContextGuard`).
    2.  Sửa cấu hình module làm lộ ra sự không tương thích dữ liệu (`Set` vs `Vec<String>` trong `ContextGuard::new`).
    3.  Sửa dữ liệu đầu vào làm lộ ra cơ chế bảo mật quá mức (`PermissionError` khi gán attribute `log`).

## 2. Câu hỏi & Khía cạnh (Questions & Aspects)
*   *Tại sao một file (`src/guards.rs`) dường như hoạt động ổn trước đó lại hỏng khi rebuild?*
    *   **Trả lời:** Có thể bản build `.pyd` cũ đang chạy trong môi trường (cached) chấp nhận các hành vi lỏng lẻo hơn, hoặc code Python và Rust đã bị lệch pha (out of sync) mà không được phát hiện cho đến khi thực hiện biên dịch lại sạch sẽ (clean build).
*   *Khía cạnh quan trọng:* **ABI Boundary (Ranh giới nhị phân)**. Đây là nơi nguy hiểm nhất. Python lỏng lẻo (Duck Typing), Rust nghiêm ngặt (Static Typing). Khi Python truyền một `set` vào hàm Rust chờ `Vec`, nó sẽ lỗi nếu không có lớp đệm xử lý thủ công.

## 3. Dữ liệu (Data)
*   Dữ liệu lỗi rất rõ ràng: `TypeError` (sai kiểu), `args missing` (thiếu tham số), `PermissionError` (chặn quyền logic).
*   Điều này chỉ ra lỗi nằm ở layer **Giao tiếp/Phiên dịch** (Interface/Translation layer), không phải logic nghiệp vụ lõi.

## 4. Khái niệm (Concepts)
*   **Ownership & Inheritance trong PyO3:** Chúng ta đã giả định sai rằng `#[pyclass(subclass)]` là đủ để Python kế thừa class Rust. Thực tế macro yêu cầu khai báo `module` để Python hiểu namespace của "Class cha".
*   **Strictness (Sự nghiêm ngặt):** `ContextGuard` của Rust không có `__dict__` dynamic như object Python thường (trừ khi bật tính năng đó). Việc cố gán `self.log` như một thuộc tính động vi phạm thiết kế struct tĩnh của Rust.

## 5. Logic (Reasoning)
*   **Suy luận:** Hệ thống Theus đang chuyển dịch từ "Python thuần" sang "Hybrid Rust".
*   **Mâu thuẫn:** Code Python test (`tests/`) vẫn viết theo tư duy Python thuần (truyền set, inject attribute tự do), trong khi Core Rust (`src/`) áp đặt kỷ luật bộ nhớ và kiểu dữ liệu.
*   **Giải pháp:** Buộc phải "nới lỏng" Rust ở lớp biên (Interface Layer) để chiều theo thói quen của Python (chấp nhận `PyAny` rồi tự loop thay vì bắt buộc `Vec`, thêm trường `log` native vào struct).

## 6. Hệ luận & Tác động (Implication & Impact)
*   **Hệ luận:** Việc phát triển Theus yêu cầu tư duy "hai hệ điều hành". Mỗi thay đổi struct trong Rust cần phải được mapping ngay lập tức sang Python wrapper và Test suite.
*   **Tác động tích cực:** Những lỗi này xảy ra lúc build/test ngăn chặn lỗi runtime khó hiểu trên production. Hệ thống hiện tại đã "cứng" và đồng bộ hơn nhiều.

## 7. Giả định (Assumptions) - Đã bị phá vỡ
*   *Giả định cũ:* "Sửa `structures.rs` là độc lập, không ảnh hưởng `guards.rs`." -> **Sai.** Cùng module biên dịch (`theus_core`), hỏng build một file là hỏng tất cả.
*   *Giả định cũ:* "Python wrapper sẽ tự lo phần ép kiểu list/set." -> **Sai.** PyO3 ở tầng dưới cùng không hỗ trợ implicit conversion từ Set sang Vec cho tham số hàm.

## 8. Góc nhìn (Perspectives)
*   **Góc nhìn Kỹ thuật:** Sửa lỗi kiểu "Whack-a-mole" (đập chuột) gây mệt mỏi ngắn hạn.
*   **Góc nhìn Kiến trúc:** Đây là quá trình "Trả nợ kỹ thuật" (Paying Technical Debt). Chúng ta đang chuẩn hóa giao diện giữa hai ngôn ngữ, trám lại các lỗ hổng thiết kế cũ. Hệ thống đã đạt được sự **Đồng nhất (Consistency)** cao hơn.
