# Chương 1: Luồng Tư Duy Chính Thức (The Formal Reasoning Model)

> *"Trước khi gõ `import pop_sdk`, bạn cần cài đặt `pop_mindset` vào não bộ."*

---

## 1.1. Bản chất: Phương trình POP (The POP Equation)

Một hệ thống phức tạp không phải là tập hợp các đối tượng tĩnh. Nó là tổng hòa của các biến đổi.
POP định nghĩa hệ thống bằng một phương trình toán học đơn giản nhưng mạnh mẽ:

```math
System = \sum (Transform \circ Context)
```

Trong đó:
*   **Transform (Biến đổi):** Là động từ. Là hành động. Là logic thuần túy.
*   **Context (Bối cảnh):** Là danh từ biếng nhác. Là dữ liệu trôi qua.
*   **$\circ$ (Composition):** Là sự kết nối, lắp ghép các biến đổi lại với nhau.

**Tại sao phương trình này quan trọng?**
Vì nó khẳng định: **Dữ liệu và Hành vi là hai thực thể riêng biệt**. Chúng không được phép trộn lẫn vào nhau (như trong OOP Class).

---

## 1.2. Hệ quy chiếu POP (The Coordinate System)

Trong không gian tư duy của POP, mọi vấn đề đều được mô hình hóa bằng 4 thành phần cơ bản.

### 1. **Context (C - Dữ liệu)**
*   **Định nghĩa:** Là "chiếc hộp" chứa dữ liệu tại một thời điểm.
*   **Tính chất:**
    *   **Dumb (Ngốc):** Chỉ chứa data (`int`, `str`, `list`, `pydantic model`), KHÔNG chứa logic.
    *   **Transparent (Minh bạch):** Nhìn vào Context là biết toàn bộ sự thật về hệ thống (State).
*   **Code Mapping:** `@dataclass`, `TypedDict`.

### 2. **Process (P - Biến đổi)**
*   **Định nghĩa:** Là một hàm thuần túy (hoặc gần thuần túy) thực hiện **một hành động duy nhất**.
*   **Công thức:** `P(C) -> C'` (Nhận Context cũ, trả về Context mới).
*   **Tính chất:**
    *   Không giữ state ngầm (Stateless execution).
    *   Không gọi Process khác trực tiếp (No direct dependency).

### 3. **Workflow (W - Dòng chảy)**
*   **Định nghĩa:** Là bản vẽ kỹ thuật nối các Process lại với nhau.
*   **Vai trò:** "Bản đồ nhận thức" (Cognitive Map). Giúp dev nhìn vào là hiểu hệ thống làm gì theo thứ tự nào.

---

## 1.3. Năm Nguyên lý Cốt lõi (The 5 Core Principles)

### Nguyên lý 1: Ý nghĩa hơn Hình dạng (Semantic > Structural)
*   **Phát biểu:** Cấu trúc dữ liệu có thể thay đổi (Evolvable), nhưng Ý NGHĨA của nó phải bất biến (Invariant).
*   **Ví dụ:** `pose` của Robot có thể đổi từ `list` sang `class`, nhưng vẫn phải là "Tọa độ".

### Nguyên lý 2: Trạng thái Mở (Open State Principle)
*   **Phát biểu:** Không có biến `private` ẩn giấu logic. Mọi trạng thái (State) phải nằm phơi bày trên Context.
*   **Formal:** `Delta_State = Visible & Explainable`.

### Nguyên lý 3: Minh bạch Nhận thức (Cognitive Transparency)
*   **Phát biểu:** Hệ thống phải được mô tả được bằng ngôn ngữ tự nhiên mà không mất thông tin.
*   **Anti-pattern:** Code class lồng nhau, gọi hàm ẩn (implicit calls).

### Nguyên lý 4: Linh hoạt có Kiểm soát (Controlled Flexibility)
*   **Phát biểu:** Bạn được phép linh hoạt (Dynamic Context), nhưng phải nằm trong vùng an toàn.
*   **Formal:** `Flexibility ∈ Safety Domain`.

### Nguyên lý 5: Phi Nhị Nguyên (Non-Binary Thinking)
*   **Phát biểu:** Đừng tư duy cực đoan "Hoặc OOP hoặc POP".
*   **Miền giá trị:** Quyết định không nằm ở 2 cực, mà nằm trong dải (spectrum) giữa Tính Cứng (Rigidity) và Tính Mềm (Flexibility).

---

## 1.4. Bài tập Tư duy: Từ OOP sang POP (Mental Shift)

**Bài toán:** Viết logic "Pha cà phê".

**Cách OOP (Tư duy Đóng gói):**
```python
class CoffeeMachine:
    # State bị giấu kín bên trong instance này
    def brew(self):
        if self._water < 10: raise Error
        self._beverage = "Coffee"
```

**Cách POP (Tư duy Dòng chảy):**
```python
# State phơi bày rõ ràng
Context = {water: 100, beans: 50, output: None}
# Biến đổi tường minh
def heat_water(ctx): ...
def extract(ctx): ...
```
**Lợi ích:** Dễ dàng chèn bước `check_ph(ctx)` vào giữa mà không sửa code cũ.

---

## 1.5. Mô hình ra quyết định (POP Decision Model)

Khi thiết kế một hệ thống POP, hãy tuân theo 10 bước tư duy sau (đây là quy trình chuẩn để không bị lạc lối):

1.  **Hệ thống đang thực hiện biến đổi nào?** (Xác định Process chính).
2.  **Biến đổi đó cần dữ liệu gì?** (Xác định Input Fields).
3.  **Context cần tiến hóa thế nào?** (Design State change).
4.  **Quan hệ giữa các biến đổi?** (Sequential, Parallel, hay Branching?).
5.  **Mức độ cần minh bạch?** (Thấp - Code nhanh, Cao - Code kỹ).
6.  **Độ phức hợp hệ thống?** (Small Tool hay Enterprise System?).
7.  **Chọn mức bất biến Context:** (Strict Typed hay Flexible Dict?).
8.  **Chọn dạng Workflow:** (Linear pipeline hay DAG phức tạp?).
9.  **Chọn mức tách trạng thái:** (Global Context hay chia nhỏ thành Domain Contexts?).
10. **Chọn công cụ thực thi:** (Python Script, POP SDK, hay Rust Engine?).

> **Tư duy ngược:** Đừng chọn công cụ (Bước 10) trước khi hiểu biến đổi (Bước 1).
