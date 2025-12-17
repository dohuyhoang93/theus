# 📘 **POP Engineering Handbook: Process-Oriented Programming for Robust Systems**

> *Phiên bản 2.0 - Tái cấu trúc theo hướng "Sổ tay Đồng hành" (Companion Handbook)*
> *Dành cho Developer, Architect và System Engineers.*

---

## **Abstract (Lời nói đầu)**

Tài liệu này không chỉ là một đặc tả kỹ thuật khô khan. Nó là một **cuốn sổ tay hướng dẫn tư duy** (mental guide) để xây dựng các hệ thống phần mềm có tính chất: **Mạnh mẽ (Robust), Minh bạch (Transparent) và Dễ tiến hóa (Evolvable).**

Chúng tôi gọi phương pháp này là **Lập trình Hướng Quy trình (Process-Oriented Programming - POP)**.

Khác với các tài liệu truyền thống bắt đầu bằng "Luật lệ", cuốn sổ tay này bắt đầu bằng **Tư duy**. Nó không yêu cầu bạn vứt bỏ OOP hay Clean Architecture. Nó chỉ ra cách để bạn sắp xếp lại chúng, biến sự phức tạp hỗn loạn thành những dòng chảy dữ liệu trong sáng.

Tài liệu được chia làm 4 phần, đi từ nhận thức đến thực hành, và cuối cùng là các tiêu chuẩn công nghiệp khắt khe.

---

# **PHẦN I: NỀN TẢNG TƯ DUY (THE MINDSET)**
> *"Đừng vội viết code. Hãy chỉnh lại cách nhìn về hệ thống trước."*

---

## **Chương 1: Luồng Tư Duy Chính Thức (Formal Reasoning Model)**

### **1.1. Hệ thống là Dòng chảy, không phải Tòa nhà**

Trong OOP, chúng ta hay tưởng tượng hệ thống như một tòa nhà với các viên gạch (Object) được xếp chồng lên nhau.
Trong POP, hãy tưởng tượng hệ thống như một **nhà máy nước** hoặc một **dây chuyền sản xuất**.

Câu hỏi đầu tiên POP đặt ra không phải là *"Class này tên là gì?"*, mà là:

> **"Dữ liệu đang chảy đi đâu và bị biến đổi như thế nào?"**

### **1.2. Bốn Trụ cột của Tư duy POP**

1.  **Process (Biến đổi):** Mọi logic đều là một hành động biến đổi dữ liệu.
2.  **Context (Môi trường):** Dữ liệu không nằm trong hàm, dữ liệu chảy qua hàm. Context là dòng sông đó.
3.  **Workflow (Bản đồ):** Đừng giấu luồng đi trong các lệnh gọi hàm lồng nhau (nested calls). Hãy vẽ nó ra.
4.  **State (Sự thật):** Trạng thái của hệ thống tại bất kỳ thời điểm nào cũng phải rõ ràng, không ẩn giấu.

---

## **Chương 2: Tuyên ngôn Kiến trúc Hợp nhất (The United Architecture)**

Đừng lo lắng rằng POP sẽ bắt bạn đập bỏ code cũ. POP và OOP là bạn, không phải thù.

### **2.1. Macro vs Micro**

Chúng ta hãy phân vai rõ ràng:

*   **POP là Quy hoạch Đô thị (Macro-Architecture):** Nó quy định các con đường chính (Workflow), các khu dân cư (Domain), và luật giao thông (Policy). Nó giúp bạn không bị lạc trong sự phức tạp tổng thể.
*   **OOP/FP là Thiết kế Nội thất (Micro-Architecture):** Bên trong một ngôi nhà (Process), bạn tùy ý dùng OOP để tổ chức code, dùng Class để gói gọn utility, dùng Functional để xử lý toán học. POP không can thiệp vào cách bạn kê bàn ghế trong nhà bạn.

### **2.2. Clean Architecture là Hệ thống Phòng thủ**

Khi dự án nhỏ, POP giúp bạn đi nhanh nhờ sự minh bạch.
Khi dự án khổng lồ, ta kết hợp POP với Clean Architecture để tạo ra các "Bức tường lửa" (Layers), bảo vệ business logic khỏi sự thay đổi của hạ tầng.

> **Lời khuyên cho Senior Dev:** Hãy dùng POP để nối các Clean Architecture Modules lại với nhau.

---

## **Chương 3: Tính Phi-Nhị-Nguyên (Non-Binary Thinking)**

Cuộc đời không chỉ có 0 và 1. Phần mềm cũng vậy. POP từ chối các tư duy cực đoan:

| Tư duy Cực đoan (Binary) | Tư duy POP (Non-Binary) |
| :--- | :--- |
| "Hoặc OOP hoặc POP" | "Dùng POP cho luồng, dùng OOP cho cấu trúc." |
| "Stateful là xấu, Stateless là tốt" | "Stateful cần thiết cho Business, Stateless tốt cho Logic. Hãy quản lý cả hai." |
| "Context phải đóng kín hoàn toàn" | "Context linh hoạt trong Process, đóng kín ở biên giới Module." |


# **PHẦN II: SỔ TAY THỰC HÀNH (THE DEVELOPER'S HANDBOOK)**
> *"Cầm tay chỉ việc: Làm thế nào để viết code đúng chuẩn POP?"*

---

## **Chương 4: Thiết kế Dữ liệu & Dòng chảy (Design Context First)**

Sai lầm phổ biến nhất: Bắt đầu bằng việc viết hàm `def process_something()`.
**POP Way:** Bắt đầu bằng việc định nghĩa dữ liệu `class SomethingContext`.

### **4.1. Ba tầng Context (Global - Domain - Local)**

Hãy tưởng tượng chiếc xe bus (Global) chở theo các hành khách (Domain) đi qua từng trạm.
*   **Global Context:** Chiếc xe bus. Chứa thông tin chung (User ID, Request ID, Config).
*   **Domain Context:** Hành khách. Đây là dữ liệu nghiệp vụ chính (Order, Payment, CV Data). Nó sống lâu dài.
*   **Local Context:** Vé xe, rác tạm. Sinh ra khi xử lý và vứt đi ngay sau đó.

### **4.2. Checklist Tư duy: Thiết kế Context**

Trước khi code, hãy tự hỏi:
1.  [ ] *Dữ liệu này có cần tồn tại sau khi Process kết thúc không?* (Nếu Có -> Domain. Nếu Không -> Local).
2.  [ ] *Process kế tiếp có cần đọc dữ liệu này không?* (Nếu Có -> Domain).
3.  [ ] *Dữ liệu này có thuộc về toàn bộ hệ thống không?* (Nếu Có -> Global).
4.  [ ] *Tôi có đang nhét logic vào trong Class Context không?* (Phải KHÔNG. Context là Dumb Data).

---

## **Chương 5: Viết Process Chuẩn (The Art of Process)**

Process là đơn vị lao động chính. Một Process tồi sẽ làm hỏng cả dây chuyền.

### **5.1. Quy tắc I/O Rõ ràng**

```python
# ❌ SAI: Process tự lôi data từ hư không (Global variable, Singleton)
def check_inventory():
    items = db.get_all() # Side effect ẩn!

# ✅ ĐÚNG: Nhận Context, Trả Context
def check_inventory(ctx: OrderContext) -> OrderContext:
    ctx.inventory_status = db.check(ctx.items)
    return ctx
```

### **5.2. Chế độ Kiểm soát & Thích ứng**

*   **Strict Mode (Kiểm soát):** Khi làm hệ thống thanh toán, y tế. Dữ liệu sai một ly, dừng ngay lập tức.
*   **Adaptive Mode (Thích ứng):** Khi làm AI, Vision. Dữ liệu thiếu một chút, hãy tự suy luận hoặc dùng giá trị mặc định.

### **5.3. Checklist Tư duy: Code Process**
1.  [ ] *Process này có làm quá 1 việc không?* (Tách nhỏ ra).
2.  [ ] *Input/Output có rõ ràng trong type hint không?*
3.  [ ] *Process có thay đổi biến toàn cục nào bên ngoài không?* (Tuyệt đối không).
4.  [ ] *Nếu input rỗng, Process có crash không hay handle gracefully?*

---

## **Chương 6: Tổ chức Code (Modules & Adapters)**

Đừng vứt tất cả vào một folder. Hãy chia module theo chức năng nghiệp vụ.

### **6.1. Pattern: Adapter mỏng**

Đừng biến Adapter thành một layer dày cộp. Adapter trong POP chỉ là "cái phễu" để gọi thư viện ngoài.
*   Process gọi Adapter.
*   Adapter gọi 3rd Party Lib / Database.
*   Adapter trả về data thô.
*   Process map data thô vào Context.

### **6.2. Cấu trúc thư mục gợi ý**

```
/payment_module
    /processes      # Các hàm xử lý
    /contexts       # Định nghĩa dữ liệu
    /adapters       # Gọi Stripe, Paypal
    workflow.yaml   # Ghép nối các bước
```

---

## **Chương 7: Nghệ thuật Kết nối (Composition Strategy)**

### **7.1. Xếp hình Lego (Linear vs Branching)**

*   **Linear (Tuần tự):** A -> B -> C. Dễ nhất, debug sướng nhất. Dùng cho 80% trường hợp.
*   **Branching (Rẽ nhánh):** Nếu A > 5 thì qua B, ngược lại qua C. Dùng `Router Process`.
*   **Dynamic (Động):** A tự quyết định bước tiếp theo là gì. Dùng cho AI agent phức tạp.

### **7.2. Lời khuyên xương máu**

> *"Cố gắng giữ luồng Linear lâu nhất có thể."*


# **PHẦN III: KIẾN TRÚC VẬN HÀNH (THE RUNTIME ARCHITECTURE)**
> *"Dành cho Architect: POP hoạt động bên dưới nắp capo như thế nào?"*

---

## **Chương 8: Cổng Hải quan (The Customs Gate Architecture)**

Đây là trái tim của POP Runtime. Tại sao gọi là "Hải quan"?
Vì Process là các "khách du lịch" ( code bên thứ 3, code của junior), còn Context là "An ninh Quốc gia".

### **8.1. Cơ chế 1: Airlock (Khoang đệm - Shadowing)**

Trước khi cho Process chạm vào dữ liệu thật:
1.  Engine tạo một bản sao (Shadow Copy) của Context.
2.  Đưa bản sao đó cho Process.
3.  Process xào nấu, chỉnh sửa bản sao đó.
4.  Process trả lại.
5.  Engine kiểm tra (Diff). Nếu an toàn -> Commit vào Context thật. Nếu lỗi -> Vứt bỏ bản sao.

-> **Kết quả:** Process không thể làm hỏng hệ thống dù có crash giữa chừng.

### **8.2. Cơ chế 2: Customs Officer (Lính gác - Schema Validation)**

Mỗi khi Process trả dữ liệu về:
*   Officer sẽ soi: *Dữ liệu format có đúng không?*
*   *Trường `price` có bị âm không?*
*   *Trường `email` có đúng định dạng không?*

Nếu sai -> **Reject**. Process bị đánh dấu Failed.

---

## **Chương 9: Concurrency & Hiệu năng (Performance Model)**

### **9.1. Robust Monolith First (Vững chắc trước, Scale sau)**

POP ưu tiên chạy trên một Node thật mạnh mẽ (Robust Monolith) hơn là vội vã chia nhỏ thành Microservices.
Tại sao? Vì **Network Latency** và **Distributed State** là kẻ thù của sự minh bạch.

### **9.2. Async & Parallelism**

*   **Async (I/O Bound):** Dùng cho gọi API, DB. POP hỗ trợ native async/await.
*   **Mô hình Actor (Tương lai):** Mỗi luồng xử lý là một Actor độc lập, giao tiếp qua mesage. Đây là hướng đi của POP 2.0 (Rust Core).

---

## **Chương 10: Tầm nhìn Hệ sinh thái (The Ecosystem)**

Chúng ta đang xây dựng một Engine 2 lớp:
1.  **Lớp Mềm (Python):** Linh hoạt, dễ code, dùng cho Business Logic, AI, Prototyping. (Hiện tại).
2.  **Lớp Cứng (Rust):** Hiệu năng cao, đảm bảo Memory Safety, dùng cho Core Engine. (Tương lai).


# **PHẦN IV: TIÊU CHUẨN CÔNG NGHIỆP (INDUSTRIAL GRADE)**
> *"Khi hệ thống không được phép sai. (Mission Critical)"*

---

## **Chương 11: An toàn & Quản trị (Safety & Governance)**

Trong môi trường công nghiệp (Robot, Tài chính, Y tế), "chạy được" là chưa đủ. Phải là "chạy đúng" và "dừng an toàn".

### **11.1. Từ điển Thuật ngữ (Industrial Mapping)**

Để dễ hiểu cho dân phần mềm:

| Thuật ngữ Công nghiệp | Thuật ngữ Phần mềm (Equivalent) | Ý nghĩa |
| :--- | :--- | :--- |
| **Local Guard** | Runtime Assertions / Pre-conditions | Kiểm tra ngay đầu vào hàm. |
| **Product QA** | Business Logic Validation | Kiểm tra output hợp lệ về nghiệp vụ. |
| **Global Interlock** | Circuit Breaker / Emergency Halt | Cầu dao tổng. Có biến là ngắt toàn hệ thống. |
| **Recipe Spec** | Dynamic Config / Feature Flag | Công thức nấu ăn (Config) nạp động. |
| **Signed Policy** | Immutable Infrastructure / Code Signing | Cam kết code không bị sửa đổi trái phép. |

### **11.2. The 4 Severity Levels (S/A/B/C)**

POP V2 định nghĩa chuẩn giao tiếp về lỗi dựa trên tiêu chuẩn công nghiệp:

*   **S (Stop/Serious):** Lỗi nghiêm trọng (Safety/Security).
    *   *Hành động:* **Interlock** (Dừng ngay lập tức). Rollback Transaction.
    *   *Ví dụ:* Chuyển tiền âm, truy cập trái phép.
    *   *Cơ chế:* `ContextGuard` chặn cứng.

*   **A (Abort/Warning):** Lỗi ngưỡng (Threshold).
    *   *Hành động:* Cảnh báo. Dừng nếu vi phạm quá N lần (Batch Reject).
    *   *Ví dụ:* Timeout API, dữ liệu thiếu trường không quan trọng.

*   **B (Block/Hold):** Lỗi quy trình (Business Logic).
    *   *Ý nghĩa:* Dữ liệu không sai về mặt kỹ thuật (Safety) nhưng đáng ngờ về mặt nghiệp vụ.
    *   *Hành động:* Trong Linear Mode, nó chặn quy trình lại (giống S) nhưng báo lỗi là "Block" để Operator biết cần kiểm tra thủ công dữ liệu input thay vì gọi Dev sửa code.
    *   *Ví dụ:* Nghi ngờ gian lận (Fraud check), Giá trị đơn hàng quá lớn bất thường (Business Anomaly).

*   **C (Continue/Info):** Thông tin.
    *   *Hành động:* Log lại và chạy tiếp. **Throttling:** Chỉ log lần vi phạm thứ 1, 10, 100... để tránh spam log.
    *   *Ví dụ:* User agent lạ.

*   **I (Ignore/Bypass):** Bỏ qua.
    *   *Hành động:* Không kiểm tra, không log. Dùng cho các object phức tạp (Adapter, Tensor) để giữ tính minh bạch trong khai báo mà không gây lỗi Runtime.
    *   *Ví dụ:* `env.camera_adapter`, `numpy.ndarray`.

### **11.3. Layered Governance (Mô hình Quản trị Đa lớp)**

Đừng chỉ check lỗi ở một chỗ. Hãy thiết lập 3 vòng phòng thủ:
1.  **Vòng 1 (Recipe Gate):** Input/Output Validation dựa trên luật S/A/B/C.
2.  **Vòng 2 (Engine Monitor):** Giám sát Process (Timeouts, Resource).
3.  **Vòng 3 (Global Interlock):** Cầu dao tổng. Tỉ lệ lỗi toàn hệ thống > 5% -> Dừng dây chuyền.

---

## **Chương 12: Chiến lược Kiểm thử (Testing Strategy)**

### **12.1. Tháp kiểm thử POP**

1.  **Unit Test (Logic):** Test từng hàm Process. Dễ viết, chạy nhanh.
    *   *Hỏi: Input A có ra Output B không?*
2.  **Integration Test (Flow):** Test cả Workflow.
    *   *Hỏi: Các Process có nói chuyện hiểu nhau không?*
3.  **Governance Test (Safety):** Test cơ chế an toàn. **(Quan trọng nhất)**
    *   *Hỏi: Nếu tôi cố tình đưa data rác vào, hệ thống có crash không hay dừng an toàn?*
    *   *Hỏi: Nếu DB chết, Interlock có bật không?*

---

## **LỜI KẾT**

POP không phải là lời giải cho mọi bài toán. Nhưng POP là lời giải cho bài toán **"Kiểm soát sự phức tạp"**.

Khi bạn cầm cuốn sổ tay này:
*   Hãy bắt đầu nhỏ (Small Monolith).
*   Hãy tư duy về Dòng chảy (Flow).
*   Và hãy để sự Minh bạch (Transparency) dẫn đường.

**Robust First. Scale Later.**
