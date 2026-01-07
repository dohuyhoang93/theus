# Chương 1: Luồng Tư Duy Theus (The Theus Mindset)

> *"Trước khi gõ `import theus`, bạn cần cài đặt `pop_mindset` vào não bộ."*

---

## 1.1. Bản chất: Phương trình Theus (The Theus Equation)

Một hệ thống tự động hóa không phải là tập hợp các đối tượng tĩnh. Nó là dòng chảy của sự biến đổi.
Theus định nghĩa hệ thống bằng một phương trình toán học đơn giản nhưng mạnh mẽ:

```math
System = \sum (Transform \circ Context)
```

Trong đó:
*   **Transform (Biến đổi):** Là động từ. Là hành động. Là logic thuần túy (Pure Logic).
*   **Context (Bối cảnh):** Là danh từ. Là dữ liệu trôi qua.
*   **$\circ$ (Composition):** Là sự kết nối, lắp ghép các biến đổi lại với nhau.

**Tại sao phương trình này quan trọng?**
Vì nó khẳng định: **Dữ liệu và Hành vi là hai thực thể riêng biệt**. Chúng không được phép trộn lẫn vào nhau (như trong OOP Class).

---

## 1.2. Hệ quy chiếu Theus (The Coordinate System)

Trong không gian tư duy của Theus, mọi vấn đề đều được giải quyết bằng 3 thành phần cơ bản:

### 1. **Context (C - Dữ liệu)**
*   **Định nghĩa:** Là "chiếc hộp" chứa dữ liệu tại một thời điểm.
*   **Tính chất:**
    *   **Dumb (Ngốc):** Chỉ chứa data (`int`, `str`, `list`), KHÔNG chứa logic.
    *   **Auditable (Kiểm toán được):** Mọi thay đổi trên Context đều được Theus ghi lại.
*   **Code Mapping:** `@dataclass`, `TypedDict`.

### 2. **Process (P - Biến đổi)**
*   **Định nghĩa:** Là một hàm thuần túy thực hiện **một hành động duy nhất**.
*   **Công thức:** `P(C) -> C'` (Nhận Context cũ, trả về Context mới).
*   **Tính chất:**
    *   **Stateless:** Không giữ trạng thái ngầm.
    *   **Isolated:** Không gọi Process khác trực tiếp.

### 3. **Workflow (W - Dòng chảy)**
*   **Định nghĩa:** Là bản vẽ kỹ thuật nối các Process lại với nhau.
*   **Vai trò:** "Bản đồ nhận thức" (Cognitive Map). Giúp dev nhìn vào file YAML là hiểu hệ thống đang làm gì.

---

## 1.3. Năm Nguyên lý Cốt lõi (The 5 Core Principles)

### Nguyên lý 1: Ý nghĩa hơn Hình dạng (Semantic > Structural)
*   **Phát biểu:** Cấu trúc dữ liệu có thể thay đổi (Evolvable), nhưng Ý NGHĨA của nó phải bất biến (Invariant).
*   **Ví dụ:** `ctx.robot.pose` có thể là `list` hay `dict`, nhưng ý nghĩa vẫn là "Tọa độ Robot".

### Nguyên lý 2: Trạng thái Mở (Open State Principle)
*   **Phát biểu:** Không có biến `private` ẩn giấu logic. Mọi trạng thái quan trọng (Business State) phải nằm phơi bày trên Context để Audit.

### Nguyên lý 3: Minh bạch Nhận thức (Cognitive Transparency)
*   **Phát biểu:** Hệ thống phải được mô tả được bằng ngôn ngữ tự nhiên.
*   **Anti-pattern:** Code class lồng nhau, gọi hàm ẩn (implicit calls).

### Nguyên lý 4: Linh hoạt trong Kỷ luật (Disciplined Flexibility)
*   **Phát biểu:** Bạn được phép linh hoạt (Dynamic Context), nhưng phải tuân thủ các cam kết (Contracts).
*   **Theus Enforce:** Nếu bạn khai báo Input, bạn không được phép phớt lờ nó.

### Nguyên lý 5: Phi Nhị Nguyên (Non-Binary Thinking)
*   **Phát biểu:** Đừng tư duy cực đoan "Hoặc Code hoặc No-Code". Theus nằm ở giữa: **Code-First for Logic, Config-First for Flow.**

---

## 1.4. Bài tập Tư duy: Từ OOP sang Theus (Mental Shift)

**Bài toán:** Viết logic "Pha cà phê".

**Cách OOP (Tư duy Đóng gói):**
```python
class CoffeeMachine:
    # State bị giấu kín bên trong instance này
    def brew(self):
        if self._water < 10: raise Error
        self._beverage = "Coffee"
```

**Cách Theus (Tư duy Dòng chảy):**
```python
# State phơi bày rõ ràng
Context = {water: 100, beans: 50, output: None}

# Biến đổi tường minh
@process(inputs=["water"], outputs=["output"])
def brew_coffee(ctx):
    if ctx.water < 10: return ctx.fail("NO_WATER")
    ctx.output = "Coffee"
```
**Lợi ích:** Dễ dàng chèn bước `audit_water_quality(ctx)` vào giữa mà không sửa code cũ.

---

## 1.5. Mô hình ra quyết định (Theus Decision Model)

Khi thiết kế một hệ thống Theus, hãy tuân theo quy trình 3 bước cốt lõi:

1.  **Define Context (Dữ liệu):** Hệ thống cần biết những gì? (Input/Output).
2.  **Define Process (Hành động):** Ai làm gì với dữ liệu đó? (Logic).
3.  **Define Workflow (Kết nối):** Thứ tự thực hiện ra sao? (Flow).

> **Lời khuyên:** Đừng bắt đầu bằng việc viết Code. Hãy bắt đầu bằng việc vẽ Dòng chảy dữ liệu (Data Flow).
