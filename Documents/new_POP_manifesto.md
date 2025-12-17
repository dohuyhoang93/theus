Dưới đây là **POP Manifesto – Process Oriented Programming Manifesto**

Tuyên ngôn này thể hiện đầy đủ:

* triết lý tư duy
* triết lý thiết kế
* triết lý kiến trúc
* nguyên tắc vận hành
* lời cam kết của người phát triển
  và **chức năng cốt lõi phân biệt POP với OOP, FP, Clean Architecture**.

---

# 🟦 **POP MANIFESTO — TUYÊN NGÔN CHÍNH THỨC CỦA PROCESS-ORIENTED PROGRAMMING**

## 🌐 **Lời mở đầu**

Process-Oriented Programming (POP) là một triết lý lập trình đặt **quy trình** (process) làm trung tâm thay cho đối tượng, hàm thuần hay module.

POP không nhằm cạnh tranh với OOP hay FP, mà nhằm cung cấp một con đường **tường minh, thực dụng và dễ bảo trì** cho mọi hệ thống – từ đơn giản đến phức tạp – bằng cách đưa **logic vận hành của hệ thống** về dạng **các bước tuần tự, dễ đọc, dễ kiểm soát, dễ giải thích và dễ chứng minh**.

POP là sự kết hợp giữa **cách tư duy của con người**, **một mô hình toán-tư duy giản dị**, và **kỷ luật thiết kế kỹ thuật**.

POP nói rằng:

> “Mọi hệ thống đều là dòng chảy của dữ liệu đi qua chuỗi các quy trình được định nghĩa rõ ràng. Hãy mô hình hóa hệ thống bằng chính dòng chảy đó.”

---

## 🟦 **1. Triết lý cốt lõi**

### **1.1. Lập trình là mô hình hóa dòng chảy**

Mọi phần mềm – từ robot, PLC, AI, backend – đều là **chuỗi hành động có chủ đích**.

Process là hình thức tự nhiên nhất để mô tả hành động.

POP coi hệ thống như một **dòng chảy**:

```
Dữ liệu vào → Biến đổi → Kiểm tra → Quyết định → Hành động → Dữ liệu ra
```

Tất cả đều được mô hình hóa thành **các bước rõ ràng có tên**, không ẩn logic trong lớp, không nhét hành vi vào dữ liệu, không nhúng điều kiện vào cấu trúc mơ hồ.

---

### **1.2. Sự tường minh là giá trị tối thượng**

> “Nếu không thể giải thích, thì không được phép triển khai.”

POP đặt **tính giải thích** lên hàng đầu:

* Mỗi process phải được mô tả bằng **một câu đơn có chủ ngữ – vị ngữ – mục tiêu**.
* Mỗi sự thay đổi trong context phải có lý do domain rõ ràng.
* Mỗi bước trong workflow phải có thể đọc được như mô tả công việc.

Không chấp nhận:

* logic bị chôn dưới lớp abstraction mơ hồ,
* mô hình dữ liệu bị đẩy vào kiểu "đa năng",
* hành vi bí mật nằm trong object hoặc callback ẩn.

Minh bạch là an toàn.
Minh bạch là dễ bảo trì.
Minh bạch là tính người trong phần mềm.

---

### **1.3. Tránh nhị nguyên cực đoan – embrace phi-nhị-nguyên**

POP không theo đuổi:

* “pure function hay nothing”
* “context bất biến hay hỏng hoàn toàn”
* “một bước – một dòng code”
* “workflow chỉ được linear”

POP khẳng định:

> “Thế giới không phải nhị nguyên, phần mềm cũng vậy.”

POP cho phép:

* mutation có kiểm soát
* branching trong process nếu minh bạch
* process lớn nếu là một khối ngữ nghĩa
* parallel step nếu dễ giải thích
* workflow động nếu có quy tắc an toàn

Điều quan trọng không phải kích thước hay purity.
Quan trọng là **ngữ nghĩa chuẩn xác và khả năng kiểm chứng**.

---

### **1.4. Dữ liệu không mang hành vi – Context không được “biết làm gì”**

Context là:

* dòng dữ liệu đi qua workflow
* trung tâm lưu trạng thái của domain
* “trạng thái của thế giới mô phỏng”

Nhưng context **không được chứa hành vi**, không được chứa logic, không được tự ý biến đổi.

Context là “dữ liệu câm”, nhưng không phải dữ liệu ngu.
Nó là **hiện trạng hệ thống**, không phải nơi giấu hành động.

---

## 🟦 **2. Triết lý thiết kế**

### **2.1. Process là đơn vị thiết kế nhỏ nhất**

Không class, không object, không method ẩn logic.
POP dùng **process** làm đơn vị cơ bản:

```
process(context) → context_moi
```

Process phải:

* làm **một việc có nghĩa**
* không phá domain
* có đầu vào/đầu ra rõ ràng (đọc/ghi context)
* kiểm tra được bằng unit test
* dễ mô tả bằng lời

---

### **2.2. Workflow là nơi kiến trúc được nhìn thấy**

Workflow thể hiện:

* luồng công việc
* rẽ nhánh
* song song
* gộp kết quả
* lặp
* thử-thất bại (retry, fallback, compensation)

Workflow là **bản đồ hệ thống**.
Ai cũng đọc được, không cần biết lập trình.

---

### **2.3. Phân rã process theo ngữ nghĩa, không theo số dòng**

Quy tắc:

* Một process chứa **một ý nghĩa**, có thể gồm nhiều bước nhỏ.
* Không ép process phải cực nhỏ.
* Không cho process quá lớn đến mức khó giải thích.

---

### **2.4. Tái sử dụng là phụ, tường minh là chính**

POP chấp nhận code lặp nếu:

* giúp tường minh
* giảm coupling
* giảm abstraction tầng tầng lớp lớp

POP phản đối “generic hóa quá đà”, vì generic thường che giấu ngữ nghĩa.

---

## 🟦 **3. Triết lý kiến trúc**

### **3.1. Ba lớp Context**

* **Global**: cấu hình, thông tin bất biến
* **Domain**: trạng thái vận hành, logic nghiệp vụ
* **Local**: dữ liệu tạm trong từng process

Ưu điểm:

* ngăn rò rỉ logic
* dễ kiểm soát thay đổi
* dễ audit

---

### **3.2. Process-safe Context Evolution**

Context phải tiến hóa có kiểm soát:

* mỗi thay đổi phải quan sát được
* không bao giờ ghi ngầm
* không bao giờ reuse field cho nghĩa khác
* các domain field phải có ý nghĩa cố định

---

### **3.3. Sơ đồ điều khiển có thể là Line, Nhánh, DAG hoặc Động**

POP chấp nhận nhiều dạng:

* **Tuyến tính**: bước sau sau bước trước
* **Rẽ nhánh**: chạy tùy điều kiện
* **Song song (DAG)**: tổng hợp kết quả nhiều nhánh
* **Động**: workflow thay đổi theo thời gian thực

Nhưng luôn phải:

* minh bạch
* dễ hiểu
* dễ trace

---

### **3.4. POP không chống OOP hay FP – nó chọn thực dụng**

POP học từ FP:

* tính thuần khiết có kiểm soát
* bất biến cục bộ
* tránh side-effect không mong muốn

POP học từ OOP:

* modularity
* grouping theo domain

POP học từ Clean Architecture:

* tách domain và adapter
* đơn hướng phụ thuộc

Nhưng POP không rập khuôn.
POP đặt process làm trung tâm thay vì class hoặc function thuần.

---

## 🟦 **4. Triết lý vận hành**

### **4.1. Phần mềm là một công việc – hãy mô tả bằng công việc**

Workflow POP được viết bằng ngôn ngữ tự nhiên:

```
- gọi: "camera.chup_anh"
- gọi: "anh.tim_vat"
- nếu: ctx.vat.tim_thay
    thì:
      - gọi: "robot.gap"
```

Không từ viết tắt.
Không ký hiệu lập trình.
Không syntax khó nhớ.

---

### **4.2. Mọi bước đều có thể kiểm toán (audit)**

POP đảm bảo rằng:

* trước mỗi process: snapshot context
* sau mỗi process: snapshot context
* delta phải tường minh

Giúp kiểm soát lỗi, kiểm soát hành vi, và phục vụ an toàn công nghiệp.

---

### **4.3. Process dễ test – workflow dễ kiểm tra**

* process có input → output rõ ràng
* workflow có thể chạy giả lập (simulation)
* toàn bộ hệ thống có thể “step-through”

---

## 🟦 **5. Cam kết của người theo POP**

Tôi cam kết:

1. Không giấu logic.
2. Không nhồi hành vi vào dữ liệu.
3. Không tạo abstraction rối rắm.
4. Không phá domain context vì sự tiện tay.
5. Không cực đoan purity hay cực đoan mutable.
6. Luôn giải thích được mọi bước của hệ thống.
7. Ưu tiên sự rõ ràng hơn sự hào nhoáng kỹ thuật.
8. Viết phần mềm để người thật hiểu được.
9. Kiểm soát thay đổi bằng lý trí, không theo thói quen.
10. Tôn trọng dòng chảy tự nhiên của dữ liệu và logic.

---

## 🟦 **6. Tuyên bố cuối cùng**

**POP là phương pháp đặt con người vào trung tâm của tư duy lập trình.**

* Con người suy nghĩ theo bước → POP mô hình hóa theo bước.
* Con người hiểu sự vật qua hành động → POP mô hình hóa hành động qua process.
* Con người cảm nhận dòng chảy → POP tổ chức hệ thống bằng dòng chảy context.

POP không phải một kỹ thuật.
POP là một **quan điểm về sự rõ ràng và trung thực trong phần mềm**.

---

# 📘 **POP Specification — Chương 1: Luồng Tư Duy Chính Thức (Formal Reasoning Model)**

---

## 1. Mục đích của Luồng Tư Duy Chính Thức

Luồng Tư Duy Chính Thức (Formal Reasoning Model – FRM) mô tả **cách POP tư duy**, không chỉ cách POP lập trình.

POP không phải:

* một ngôn ngữ
* một framework
* một pattern
* một kiến trúc

POP là **một phương pháp tư duy** về hệ thống phức hợp thông qua:

* process (biến đổi)
* context (môi trường dữ liệu)
* workflow (dòng chảy)
* explicit state (tính tường minh)
* phi-nhị-nguyên (non-binary)
* tương thích domain (domain-coherent)

FRM định nghĩa **logic nền tảng** chi phối mọi quyết định thiết kế trong POP.

---

## 2. Bản chất của Luồng Tư Duy POP

### **2.1. Hệ thống là chuỗi biến đổi, không phải cấu trúc tĩnh**

POP xem mọi hệ thống, bất kể dạng nào, đều có thể mô tả bằng:

1. **Các biến đổi (processes)**
2. **Dòng dữ liệu (context flow)**
3. **Mối quan hệ giữa các biến đổi (workflow/graph)**

→ Điều cốt lõi không nằm ở “module”, “object” hay “component”.
→ Điều cốt lõi là **sự vận động**.

---

### **2.2. Process là đối tượng tư duy đầu tiên**

POP bắt đầu bằng câu hỏi:

> “Bước này thực chất đang làm gì?”

Không hỏi:

* class là gì?
* interface là gì?
* object đại diện cho ai?
* entity có method nào?

Trong POP, đơn vị tư duy gốc là:

```
Process = một biến đổi rõ ràng, mô tả được bằng một câu đơn
```

---

### **2.3. Context là môi trường, không phải đối tượng**

Context trong POP không phải object/struct chứa behavior.

Nó là:

* môi trường dữ liệu
* đối tượng trung lập
* không có logic
* không có quyền tự quyết
* không có ai “sở hữu” nó

Một cách hình thức:

```
Process: f
Context: C

f: C → C'
```

---

### **2.4. Workflow là “lược đồ tư duy” của hệ thống**

Workflow POP không chỉ là control flow.

Nó là **bản đồ nhận thức**:

* giúp nhìn rõ hệ thống làm gì
* theo thứ tự nào
* với biến đổi nào
* trạng thái thay đổi ra sao
* logic nằm ở đâu

Workflow trong POP là “sơ đồ tư duy chính thức”.

---

### **2.5. POP tránh mọi logic ẩn**

POP formalism yêu cầu:

* không có behavior giấu trong object
* không có side-effect ẩn
* không có động lực ngầm
* không có polymorphism che giấu
* không có inheritance phức tạp

Tất cả đều phải **hiển lộ**.

---

## 3. Tính Phi-Nhị-Nguyên (Non-Binary Thinking)

POP chống lại tư duy nhị nguyên như:

* hoặc bất biến hoặc loạn
* hoặc pipeline hoặc graph
* hoặc context cố định hoặc tùy ý
* hoặc functional hoặc imperative
* hoặc OOP hoặc anti-OOP
* hoặc đơn nhiệm hoặc đa nhiệm

**POP không bắt buộc chọn 1 — POP mô tả “biên độ lựa chọn hợp lý”.**

Dạng hình thức:

```
A không loại B
A và B tạo thành miền giá trị (value domain)
Quyết định nằm trong miền, không nằm ở cực
```

Đây là nền tảng tư duy của POP:

> **POP không dựng hàng rào.
> POP dựng không gian lựa chọn hợp lý.**

---

## 4. Nguyên lý “Biến đổi + Bối cảnh” (Transform + Context Principle)

Tư duy chính thức của POP xoay quanh phương trình trí tuệ sau:

```
Hệ thống = ∑ (Biến đổi ∘ Bối cảnh)
```

Trong đó:

* Biến đổi (process) = hành động
* Bối cảnh (context) = dữ liệu nền
* Workflow = thứ tự + quan hệ

→ Từ đây, mọi hệ thống được mô hình hóa bởi:

1. Các biến đổi (transformations)
2. Mối liên hệ giữa chúng (composition)
3. Sự tiến hóa của dữ liệu (state evolution)

Đây là tư duy tương thích với:

* functional core
* unix pipeline
* dataflow system
* DSP
* robotics
* ML pipeline

Không hề xung đột.

---

## 5. Nguyên lý “Ý nghĩa hơn Hình dạng” (Semantic > Structural Principle)

Trong tư duy nhị nguyên, người ta coi:

* schema phải cố định
* hoặc schema phải tự do

Trong POP:

> **Ý nghĩa dữ liệu phải ổn định
> Nhưng hình dạng (shape) có quyền tiến hóa.**

Ví dụ:

* trường `pose` có thể từ vector → struct → record
* nhưng ý nghĩa của `pose` (tọa độ để robot pick) không đổi

Formal:

```
Semantic(C) = invariant
Structure(C) = evolvable
```

---

## 6. Nguyên lý “Minh bạch nhận thức” (Cognitive Transparency Principle)

Một hệ thống chỉ được coi là POP-compliant khi:

* Developer đọc vào hiểu ngay
* Không cần giải mã kiến trúc
* Không cần lần theo đồ thị kế thừa
* Không cần mở 10 class để xem logic

Định nghĩa formal:

```
Minh bạch = Khả năng mô tả hệ thống bằng ngôn ngữ tự nhiên 
            mà không mất thông tin và không mâu thuẫn.
```

---

## 7. Nguyên lý “Trạng thái mở” (Open State Principle)

Trong POP:

> Trạng thái không được giấu.
> Trạng thái phải nhìn thấy, mô tả được, và ghi dấu qua từng bước.

State có thể:

* thay đổi
* tiến hóa
* mở rộng

Nhưng:

* không được ẩn
* không được sinh ra bất thình lình
* không được gói trong object
* không được giấu trong closure

Formal:

```
∀ process f:
    State_before is visible
    State_after is visible
    ΔState must be explainable
```

---

## 8. Nguyên lý “Linh hoạt có kiểm soát” (Controlled Flexibility Principle)

POP cho phép:

* context thay đổi cấu trúc
* process nhận một phần context
* workflow phân nhánh, song song, quay lui
* pipeline lỏng hoặc pipeline chặt

Nhưng:

> Tính linh hoạt phải nằm trong **không gian an toàn**,
> và phải giữ được **minh bạch nhận thức**.

Formal:

```
Flexibility ∈ Safety Domain
```

POP không quy định shape — POP quy định **giới hạn an toàn**.

---

## 9. Mô hình lựa chọn trong POP (POP Decision Model)

Khi thiết kế hệ thống POP, việc ra quyết định diễn ra theo thứ tự:

1. **Hệ thống đang thực hiện biến đổi nào?**
2. **Biến đổi đó cần dữ liệu gì?**
3. **Context cần tiến hóa thế nào để phục vụ biến đổi?**
4. **Quan hệ giữa các biến đổi ra sao?**
5. **Mức độ cần minh bạch — thấp, trung bình, hay cao?**
6. **Độ phức hợp của hệ thống thuộc loại nào?**
7. **Chọn mức bất biến context hợp lý**
8. **Chọn dạng workflow phù hợp**

   * linear
   * branching
   * DAG
   * feedback loop
9. **Chọn mức tách trạng thái (state layering)**
10. **Chọn nền tảng kỹ thuật để hiện thực hóa**

Tức là tư duy POP đi từ:

> **Biến đổi → Dữ liệu → Dòng chảy → Mức minh bạch → Hình thức thực thi.**

Không bao giờ ngược lại.

---

## 10. Mục tiêu của FRM (Formal Reasoning Model)

1. Bảo vệ POP khỏi cực đoan.
2. Định nghĩa tư duy phi nhị nguyên.
3. Cho phép POP hoạt động trên hệ thống nhỏ và lớn.
4. Tránh pop thành “giáo điều kiểu OOP/Clean Architecture”.
5. Cho phép tiến hóa kiến trúc mà không phá nguyên tắc POP.
6. Mở đường cho các phần sau: context layers, process decomposition, workflow graph.

---

## 11. Kết luận

FRM đưa POP lên tầm:

* Không còn là lựa chọn kỹ thuật
* Không còn là “anti-OOP”
* Không còn là pipeline đơn thuần

Mà trở thành **một phương pháp tư duy về hệ thống phức hợp**, dựa trên:

* biến đổi
* bối cảnh
* ý nghĩa
* minh bạch
* phi nhị nguyên
* tiến hóa dữ liệu
* kiểm soát độ phức hợp
* an toàn logic

Triết lý POP sẽ không bao giờ bị “bóng ma cực đoan” ám ảnh như OOP, ECS, Clean Architecture đã gặp phải.

---

# 📘 **Chương 2 — Mô hình Context Layer (Global / Domain / Local)**

---

## 2.1. Mục tiêu của mô hình Context Layer

Mô hình Context Layer nhằm giải quyết hai vấn đề cốt lõi:

1. **Tránh “God Context”** — context phình to mất kiểm soát.
2. **Cho phép context tiến hóa mà vẫn giữ tính minh bạch và an toàn.**

POP không xem context là một cấu trúc thống nhất bất biến, mà là **một môi trường đa lớp**, mỗi lớp phục vụ một mục đích khác nhau.

---

## 2.2. Ba lớp context trong POP

POP định nghĩa context gồm **ba lớp chính**:

```
[Global Context]
[Domain Context]
[Local Context]
```

Mỗi lớp có vai trò, vòng đời, và phạm vi ảnh hưởng khác nhau.

---

## 2.3. Global Context (GC)

### **Định nghĩa:**

Global Context chứa dữ liệu xuyên suốt toàn bộ workflow, không phụ thuộc từng process.

### **Đặc điểm:**

* tồn tại từ đầu đến cuối workflow
* thay đổi ít, hoặc không thay đổi
* không phụ thuộc domain
* không phụ thuộc tác vụ cụ thể

### **Ví dụ:**

* job_id
* timestamp
* user_id / session_id
* pipeline configuration
* global flags
* permission state (trong automation)

### **Quy tắc:**

* Không được chứa dữ liệu domain
* Không được chứa dữ liệu ngắn hạn
* Không được phình to theo logic cụ thể
* Được coi là “khung xương” của context

### **Vai trò:**

Tạo **tính ổn định** và **tính nhận diện** cho toàn pipeline.

---

## 2.4. Domain Context (DC)

### **Định nghĩa:**

Domain Context chứa dữ liệu phục vụ logic nghiệp vụ của hệ thống, thay đổi tùy theo domain.

### **Đặc điểm:**

* thay đổi theo từng process
* mang theo dữ liệu domain
* có vòng đời bằng vòng đời của workflow
* không được chứa trạng thái tạm thời thuộc local scope

### **Ví dụ:**

Robotics:

* pose
* target_position
* object_features
* collision_map

AI pipeline:

* feature_vector
* model_output
* probabilities
* embedding

PLC/Industrial:

* pressure
* valve_state
* sensor_data

### **Quy tắc:**

* Là nơi chính mà process đọc/ghi dữ liệu
* Phải minh bạch: DC trước và sau mỗi process phải có thể so sánh
* Không được chứa metadata vặt (để local context xử lý)

### **Vai trò:**

DC là **trái tim** của workflow — nơi lưu dấu sự tiến hóa của logic.

---

## 2.5. Local Context (LC)

### **Định nghĩa:**

Local Context chứa dữ liệu tạm phục vụ cho một process cụ thể.

### **Đặc điểm:**

* tồn tại trong phạm vi một process
* không truyền qua các process
* có thể là bất kỳ cấu trúc nào (flexible)
* dùng để làm giảm phình to domain context

### **Ví dụ:**

* buffer tạm cho vision
* intermediate tensor
* temporary flags
* raw I/O snapshot từ PLC
* giá trị tính toán không cần lưu vào domain

### **Quy tắc:**

* Không được ghi vào global hoặc domain context
* Tự giải phóng sau process
* Không được phép thay đổi cấu trúc context chính
* Không được phép dùng để che giấu logic

### **Vai trò:**

LC **ngăn domain context phình to**, đồng thời cho phép POP linh hoạt hơn.

---

## 2.6. Lợi ích của mô hình 3-layer context

### ✔ Tránh God Context

Domain context không phình lung tung.

### ✔ Process nhỏ hơn và dễ test hơn

Mỗi process dùng local context để xử lý ngắn hạn.

### ✔ Minh bạch

Dòng chảy domain vẫn theo đúng pipeline POP.

### ✔ Tối ưu cho systems engineering

Bạn có dữ liệu dài hạn (global), biến đổi trung hạn (domain), và dữ liệu cục bộ (local).

### ✔ Hỗ trợ phi-nhị-nguyên

Không cần cực đoan “một context cho tất cả”.

---

## 2.7. Sơ đồ chính thức

```
┌───────────────────────────────────┐
│            Global Context         │
└───────────────┬───────────────────┘
                │
                ▼
       ┌───────────────────┐
       │   Domain Context  │
       └────────┬──────────┘
                │
    ┌───────────┴───────────┐
    │          Process       │
    └───────────┬───────────┘
                │
                ▼
       ┌───────────────────┐
       │   Local Context   │
       └───────────────────┘
```

Global và Domain di chuyển qua pipeline.
Local sinh ra và biến mất theo từng process.

---

# 📘 **Chương 3 — Hệ thống Quy Tắc An Toàn Khi Context Tiến Hóa**

---

## 3.1. Tại sao cần quy tắc tiến hóa context?

Vấn đề phổ biến:

* context trở nên hỗn loạn
* mỗi process thêm field
* không ai xóa field
* schema thay đổi không kiểm soát
* context trở thành “bãi rác dùng chung”

Để giữ POP minh bạch, context cần **quy tắc tiến hóa** khoa học.

---

## 3.2. Nguyên lý cốt lõi: “Tiến hóa có kiểm soát” (Controlled Evolution)

Context được phép tiến hóa, nhưng phải:

1. **Minh bạch (transparent)**
2. **Có lý do hợp lệ (justified)**
3. **Không phá workflow (safe)**
4. **Không gây ambiguity (unambiguous)**
5. **Không làm tăng độ phức tạp bất hợp lý (bounded)**
6. **Không phá consistency của domain (coherent)**

---

## 3.3. Sáu Quy Tắc Tiến Hóa An Toàn (The Six Context Safety Rules)

### **Rule 1 — Every context mutation must be explicit**

Không có mutation ngầm.
Không có “magic field”.

#### Yêu cầu:

* phải ghi log
* phải được test
* phải được review

---

### **Rule 2 — Domain Context chỉ được thêm field khi field đó có nghĩa trong domain**

Không được thêm field “tiện tay”.

Nếu field không phục vụ domain logic → Local Context.

#### Ví dụ sai:

```
domain.temp_value
domain.raw_image_buffer
```

#### Ví dụ đúng:

```
domain.target_pose
domain.pressure_drop
```

---

### **Rule 3 — Không process nào được xóa/override field mà không lý do domain rõ ràng**

Operation “ghi đè một phần domain” phải được mô tả bằng câu:

> “Process này thay đổi field X vì lý do Y trong quy tắc domain.”

Nếu không giải thích được → vi phạm POP.

---

### **Rule 4 — Schema của Domain Context phải tiến hóa theo version**

Mỗi thay đổi về:

* tên field
* kiểu dữ liệu
* cấu trúc lồng nhau

… đều phải có semantic version:

```
domain.version = 2
```

Không có version → không POP-compliant.

---

### **Rule 5 — Local Context không được lan ra ngoài phạm vi process**

Nếu Local Context lan ra:

* Domain Context phình
* Global Context bị ô nhiễm
* process coupling xảy ra
* pipeline mất minh bạch

Quy tắc nghiêm:

```
LocalContext MUST NOT be inserted into DomainContext or GlobalContext.
```

---

### **Rule 6 — Các thay đổi context phải giữ tính nhất quán ngữ nghĩa (semantic consistency)**

Field có thể:

* thêm
* bỏ
* đổi
* gộp
* chia nhỏ

Nhưng **nghĩa** không được thay đổi tùy tiện.

Ví dụ:

* `pose`, `target_pose`, `object_pose` phải luôn nói về tọa độ
* `pressure` luôn là áp suất
* `features` luôn là vector đặc trưng

Không được dùng lại field cũ cho nghĩa mới.

---

## 3.4. Bộ Kiểm Tra Tiến Hóa (Evolution Safety Checklist)

Mọi thay đổi của context phải trả lời **5 câu hỏi**:

### Q1 — Việc tiến hóa này có phục vụ domain không?

Nếu không → Local Context.

### Q2 — Nghĩa dữ liệu có bị mơ hồ không?

Nếu có → tách field hoặc đổi tên.

### Q3 — Process khác có bị ảnh hưởng không?

Nếu có → update workflow.

### Q4 — Có cần versioning không?

Nếu thay đổi shape → Có.

### Q5 — Tính minh bạch có bị suy giảm không?

Nếu có → sai POP.

---

## 3.5. Bộ Quy Tắc Đồng Đẳng (Context Parity Rules)

Để workflow không bị méo thông tin, POP đưa ra nguyên tắc:

> **Context trước và sau một process phải có thể so sánh được về ý nghĩa.**

Không cần giống hệt shape, nhưng:

* phải cùng mô tả một “thế giới logic”
* không được làm domain nhảy ngữ cảnh
* không được tạo trạng thái không tiếp nối

---

## 3.6. Tiến hóa Domain Context theo chu kỳ

Domain Context nên có chu kỳ:

1. **Initiate**
2. **Enrich**
3. **Transform**
4. **Conclude**

Không được:

* revert lung tung
* tạo vòng bất đồng bộ
* làm domain đảo chiều logic

---

## 3.7. Sơ đồ chính thức cho tiến hóa context

```
Context(C0)
   |
   | Process f1 → Δ1
   v
Context(C1)
   |
   | Process f2 → Δ2
   v
Context(C2)
   |
   | Process f3 → Δ3
   v
Context(C3) ... Cn
```

Trong đó:

* Δi = thay đổi rõ ràng, đúng domain, không mơ hồ
* Ci luôn hợp lệ với domain (semantic integrity)

---

## 3.8. Tương thích với lối tư duy phi-nhị-nguyên

Quy tắc tiến hóa đảm bảo:

* context vừa linh hoạt vừa an toàn
* process vừa độc lập vừa nhất quán
* workflow vừa rõ ràng vừa mở rộng được
* không cần absolute context invariance
* không cần free-form context

Một dạng **trung đạo có kiểm soát**.

---

## 3.9. Tổng kết

Hai chương này đặt nền tảng cho:

* sự tiến hóa có kiểm soát của dữ liệu
* sự linh hoạt không phá hỏng minh bạch
* cách POP xử lý hệ thống lớn mà không rơi vào cực đoan

Context Layer = “cấu trúc đa tầng của thế giới”.
Context Evolution Rules = “luật vật lý của thế giới đó”.

---

# 📘 **Chương 4 — Quy tắc Phân Rã Process Phi-Nhị-Nguyên (Non-Binary Process Decomposition Rules)**

---

## 4.1. Mục tiêu

Nguyên tắc phân rã process phi-nhị-nguyên (NB-PDR) nhằm tránh hai cực đoan:

* **Quá cứng (strict)**: process quá nhỏ → pipeline quá dài → mất toàn cảnh.
* **Quá lỏng (loose)**: process quá lớn → ẩn logic → mất minh bạch.

NB-PDR cung cấp một **không gian lựa chọn hợp lý** cho kích thước process, dựa trên:

* ý nghĩa logic
* nhu cầu domain
* mức độ minh bạch cần thiết
* mức độ phức hợp
* mức độ thay đổi dự kiến trong tương lai

---

## 4.2. Định nghĩa Process trong POP

Trong POP:

```
Process = một đơn vị biến đổi có ý nghĩa độc lập, 
được mô tả bằng 1 mệnh đề đơn không mơ hồ.
```

Không yêu cầu:

* process phải tuyệt đối đơn nhiệm (one-command-only)
* process phải thuần (pure)
* process phải cô lập hoàn toàn

Nó chỉ cần **minh bạch** và **giải thích được**.

---

## 4.3. Phi-Nhị-Nguyên trong phân rã

NB-PDR nhấn mạnh:

> **Một process không nhất thiết phải “một hành động – một dòng code”.
> Một process có thể chứa *một cụm logic có liên kết ngữ nghĩa* (semantic cluster).**

Tức là process được phân rã theo **ngữ nghĩa**, không phải theo **kích thước**.

---

## 4.4. Quy tắc 1 — Phân rã theo “khối ý nghĩa” (Semantic Cluster Rule)

### Định nghĩa:

Một process nên được phân rã khi nó chứa **nhiều ý nghĩa khác nhau**,
nhưng **không cần phân rã** nếu các hành động tạo nên **một ý nghĩa chung**.

### Ví dụ:

Process "detect_object_pose" có thể gồm:

* tiền xử lý ảnh
* phân đoạn
* tính tọa độ
* trả object_pose

→ Tất cả cùng mô tả *một khối ý nghĩa thống nhất*.
→ Không cần tách thành 4 process.

Trái lại:

Process “detect_pose_and_save_to_db” chứa 2 ý nghĩa khác nhau:

1. nhận dạng pose
2. ghi dữ liệu vào DB

→ Phải tách.

---

## 4.5. Quy tắc 2 — Phân rã theo khả năng giải thích (Explainability Rule)

> **Nếu một process không thể được mô tả bằng *một câu đơn, có chủ ngữ – vị ngữ rõ ràng*, thì phải phân rã.**

Ví dụ sai:
“Phân tích dữ liệu và đưa ra quyết định điều khiển robot để tránh va chạm dựa vào bản đồ hiện tại.”

→ Không thể mô tả bằng 1 câu đơn → tách.

Ví dụ đúng:
“Đánh giá nguy cơ va chạm cho robot.”

→ Một ý nghĩa → giữ nguyên.

---

## 4.6. Quy tắc 3 — Phân rã theo độ biến động (Volatility Rule)

Process có độ biến động khác nhau phải được tách riêng.

### Ví dụ:

* logic xử lý vision thường thay đổi nhiều
* logic kiểm tra áp suất ít thay đổi
* logic điều khiển robot có chu kỳ ổn định hơn

=> Nếu ghép chung → coupling sinh ra → tăng chi phí bảo trì.

NB-PDR yêu cầu:

> **Các phần có tốc độ thay đổi khác nhau phải được phân rã thành process riêng.**

---

## 4.7. Quy tắc 4 — Phân rã theo mức rủi ro (Risk Segregation Rule)

Những hành động có rủi ro khác nhau (I/O, safety-critical, pure logic) phải được chia tách.

### Ví dụ trong PLC:

* đọc cảm biến (risk: medium)
* quyết định an toàn (risk: high)
* log dữ liệu (low risk)

→ Không được nằm trong một process duy nhất.

---

## 4.8. Quy tắc 5 — Process có thể chứa logic rẽ nhánh *nhưng phải minh bạch* (Transparent Branching Rule)

POP **không cấm branching trong process**.
POP chỉ cấm **branching không thể giải thích hoặc branch ẩn ngữ nghĩa**.

Ví dụ đúng:

```
if pressure < threshold:
    ctx.warning = True
```

→ Ngữ nghĩa rõ: “phát hiện áp suất thấp”.

Ví dụ sai:

```
if type(x) != expected_type:
    silently_fix()
```

→ Branch ẩn ý → không minh bạch → tách hoặc viết lại.

---

## 4.9. Quy tắc 6 — Process cho phép sử dụng Local Context thoải mái

(miễn không làm bẩn domain)

Local context giúp process tránh phình domain context.

NB-PDR cho phép process chứa:

* buffer tạm
* intermediate data
* raw I/O
* temporary compute target

Miễn mọi thứ:

* không ảnh hưởng domain
* không lan sang global
* biến mất sau process

---

## 4.10. Quy tắc 7 — Kích thước process được quyết định bởi “độ phức hợp nhận thức” (Cognitive Load Rule)

Nếu process:

* dễ đọc
* dễ giải thích
* dễ test
* không làm developer bị “overload nhận thức”

→ Giữ nguyên.

Nếu process:

* khó đọc
* khó giải thích bằng lời
* khó test độc lập
  → Tách.

---

## 4.11. Kết luận phân rã phi nhị nguyên

Phân rã process trong POP không chạy theo:

* độ dài
* số dòng
* số thao tác
* purity
* cấu trúc thủ tục

Phân rã dựa trên:

* **ngữ nghĩa**
* **mức rủi ro**
* **mức biến động**
* **khả năng giải thích**
* **tính minh bạch**

---

# 📘 **Chương 5 — Quy tắc An Toàn Khi Process Tương Tác Với Context**

---

## 5.1. Mục tiêu

Hệ thống POP yêu cầu:

* context rõ ràng
* process rõ ràng
* tương tác giữa chúng **càng minh bạch càng tốt**

Chương này xác định các **safety rules** đảm bảo:

* context không bị phá hủy
* không sinh logic ẩn
* không gây coupling
* không làm méo domain
* không tạo trạng thái không thể dự đoán

---

## 5.2. Quy tắc 1 — Process phải khai báo rõ phần của context mà nó dùng

(Explicit Context Access Rule)

Process phải khai báo:

* phần của Global Context cần đọc/ghi
* phần của Domain Context cần đọc/ghi
* không được đụng Local Context ngoài phạm vi process

Ví dụ (đúng):

```
read: domain.pose, domain.depth_map
write: domain.collision_probability
```

Nếu process đọc hoặc ghi field không khai báo → lỗi POP.

---

## 5.3. Quy tắc 2 — Process chỉ được phép thay đổi Domain Context vì lý do domain

(Domain Justification Rule)

Nếu process thay đổi một phần domain mà không có lý do liên quan đến domain → sai.

Ví dụ sai:

* xóa `target_pose` vì “không dùng nữa”
* đổi `features` thành dạng khác không chuẩn
* ghi `raw_image` vào domain

Domain context chỉ tồn tại để phục vụ domain logic.

---

## 5.4. Quy tắc 3 — Không process nào được thay đổi Global Context

(Global Invariance Rule)

Global context bị xem là **bất biến vận hành**.

Process có thể đọc, nhưng **không được ghi**.

Nếu phải thay đổi global context:

* tạo version mới
* khởi tạo workflow mới

Không được mutate trực tiếp.

---

## 5.5. Quy tắc 4 — Mọi thay đổi Domain Context phải có thể quan sát

(Observable Mutation Rule)

POP không cấm mutation, nhưng bắt buộc:

* trước process: domain_before
* sau process: domain_after
* delta = sự khác biệt có thể mô tả

Không được:

* sửa “ngầm”
* sửa mà không để lại dấu
* sửa nhiều phần không liên quan

---

## 5.6. Quy tắc 5 — Không được tạo field mới tùy tiện

(Controlled Field Introduction Rule)

Field mới chỉ được tạo khi:

* liên quan domain
* thực sự cần
* không gây overlap semantic với field khác
* đã cập nhật version schema

Tránh “field rác”.

---

## 5.7. Quy tắc 6 — Không được reuse field cho nghĩa mới

(Semantic Integrity Rule)

Nếu một field từng đại diện cho “pose”,
không được reuse để chứa:

* vector điểm ảnh
* trạng thái cảm biến
* chuỗi trạng thái khác

Nếu muốn nghĩa mới → tạo field mới.

---

## 5.8. Quy tắc 7 — Process không được phá vỡ cấu trúc domain

(Structural Preservation Rule)

Process có thể:

* thêm field
* sửa field
* cập nhật giá trị

Nhưng không được:

* thay đổi cấu trúc domain theo cách phá workflow
* đổi kiểu dữ liệu quan trọng
* đổi định dạng không đồng nhất
* biến domain thành cấu trúc không còn mô tả đúng thế giới domain

---

## 5.9. Quy tắc 8 — Process không được gây side-effect ẩn vào context

(No Hidden Side-Effect Rule)

Cấm:

* tự động chuẩn hóa dữ liệu mà không khai báo
* tự động xóa field
* tự động tạo metadata
* tự động chuyển đổi kiểu
* tự động tạo object chứa behavior

---

## 5.10. Quy tắc 9 — Process phải bảo toàn “dòng ngữ nghĩa”

(Semantic Flow Conservation Rule)

Sau mỗi process, domain context vẫn phải nằm trong:

> **cùng một thế giới ngữ nghĩa**, không bị “dịch chuyển hệ tọa độ tư duy”.

Process không được:

* biến domain từ dạng robotics sang dạng vision một cách không minh bạch
* đổi “pose” thành “image analysis result”
* đổi “pressure” thành “raw PLC log”

Nếu cần chuyển domain → dùng process chuyển domain theo nghĩa tường minh.

---

## 5.11. Quy tắc 10 — Process chỉ được truy cập dữ liệu cần thiết

(Access Minimization Rule)

Không đọc toàn bộ context nếu không cần.

Nếu process chỉ cần:

* pose
* camera intrinsics

… thì chỉ được đọc hai field đó.

Tránh coupling không cần thiết.

---

## 5.12. Kết luận

POP không chống lại:

* mutation
* branching
* local state
* đa dạng context
* tiến hóa cấu trúc

POP chỉ chống lại:

* mơ hồ
* ẩn logic
* rác semantic
* phá workflow
* coupling lung tung
* mất minh bạch nhận thức

Hai chương này bảo đảm process:

* minh bạch
* có thể audit
* có thể test độc lập
* không phá domain
* không tạo “context hỗn loạn”

---

# 📁 **Chương 6 - Cách tổ chức code POP — nguyên tắc + mẫu thư mục + ví dụ (Python & Rust)**

## Nguyên tắc tổ chức code POP

1. **Module theo domain/module (feature module)** — mỗi module chứa:

   * `context` (Domain Context types)
   * `processes` (hàm process / impl)
   * `local` (helpers, local context builders)
   * `tests`
2. **Registry tách riêng** — mapping tên → function; có thể load động (plugin).
3. **Engine tách riêng** — runner đọc workflow (DSL/JSON/YAML), validate, execute, trace, version.
4. **Adapters / IO ở layer ngoài cùng** — drivers (PLC, camera, DB) chỉ ở layer adapter, không chứa domain logic.
5. **Schema & versioning** — mỗi Domain Context có version; thay đổi phải tăng version.
6. **Logging & Audit** — engine lưu trước/sau mỗi process, deltas.
7. **Local Context** chỉ tồn tại trong scope process (không push vào domain context unless explicit).

---

## Mẫu cấu trúc dự án (high-level)

```
pop_project/
├─ engine/
│  ├─ runner.py / runner.rs
│  ├─ registry.py
│  ├─ loader.py
│  └─ validator.py
├─ adapters/
│  ├─ camera_adapter.py
│  ├─ plc_adapter.py
│  └─ db_adapter.py
├─ modules/
│  ├─ vision/
│  │  ├─ context.py
│  │  ├─ processes.py
│  │  └─ tests/
│  └─ robot/
│     ├─ context.py
│     ├─ processes.py
│     └─ tests/
├─ workflows/
│  ├─ pick_and_place.yaml
│  └─ calibration.yaml
├─ schemas/
│  └─ domain_context_v1.json
├─ cli.py
└─ README.md
```

### Quy ước:

* `modules/*` = feature modules; mỗi module export processes cho registry.
* `engine/registry` = nơi duy trì mapping tên → callable.
* `workflows/` = DSL/JSON/YAML.

---

## Ví dụ cụ thể — Python (minimal, idiomatic)

`modules/vision/context.py`

```python
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class VisionDomainContextV1:
    job_id: str
    image_id: Optional[str] = None
    image_bytes: Optional[bytes] = None
    keypoints: Optional[List[float]] = None
    features: Optional[List[float]] = None
    version: int = 1
```

`modules/vision/processes.py`

```python
from .context import VisionDomainContextV1
from typing import Dict

def load_image(ctx: VisionDomainContextV1, env: Dict) -> VisionDomainContextV1:
    # local context usage
    img = env['camera'].capture(ctx.image_id)
    ctx.image_bytes = img
    return ctx

def detect_keypoints(ctx: VisionDomainContextV1, env: Dict) -> VisionDomainContextV1:
    img = ctx.image_bytes
    kp = env['vision_lib'].detect(img)
    ctx.keypoints = kp
    return ctx

def extract_features(ctx: VisionDomainContextV1, env: Dict) -> VisionDomainContextV1:
    ctx.features = env['feat_extractor'](ctx.keypoints)
    return ctx
```

`engine/registry.py`

```python
REGISTRY = {}

def register(name):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco
```

`modules/vision/processes.py` (with register)

```python
from engine.registry import register

@register("vision.load_image")
def load_image(ctx, env): ...
# ...
```

`engine/runner.py`

```python
import yaml
from engine.registry import REGISTRY

def run_workflow(workflow_path: str, ctx, env):
    wf = yaml.safe_load(open(workflow_path))
    for step in wf['steps']:
        if isinstance(step, str):
            fn = REGISTRY[step]
            before = repr(ctx)
            ctx = fn(ctx, env)
            # log delta: compare before/after or use snapshot
        elif isinstance(step, list): # parallel or grouped
            for sub in step:
                ctx = REGISTRY[sub](ctx, env)
    return ctx
```

> Ghi chú: thực tế engine cần snapshot before/after, schema validation, error handling, retries.

---

## Ví dụ cụ thể — Rust (sketch)

Rust sẽ có cấu trúc tương tự nhưng dùng traits, function pointers, và serde cho context.

`modules/vision/src/context.rs`

```rust
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct VisionDomainContextV1 {
    pub job_id: String,
    pub image_id: Option<String>,
    pub image_bytes: Option<Vec<u8>>,
    pub keypoints: Option<Vec<f32>>,
    pub features: Option<Vec<f32>>,
    pub version: u32,
}
```

`engine/registry.rs`

```rust
use crate::context::VisionDomainContextV1;
use serde_json::Value;
use std::collections::HashMap;
type ProcessFn = fn(VisionDomainContextV1, &Env) -> VisionDomainContextV1;

pub struct Registry {
    map: HashMap<String, ProcessFn>,
}
```

`engine/runner.rs`

```rust
pub fn run_workflow(reg: &Registry, wf: &Workflow, mut ctx: VisionDomainContextV1, env: &Env) -> VisionDomainContextV1 {
    for step in &wf.steps {
        match step {
            Step::Name(n) => {
                let f = reg.get(n).unwrap();
                let before = ctx.clone();
                ctx = f(ctx, env);
                // compute delta, log
            }
            Step::Group(group) => {
                for s in group { ... }
            }
        }
    }
    ctx
}
```

> Rust chú trọng vào: typesafety cho Context, serde versioning, zero-cost abstractions.

---

## Kiến nghị triển khai

* Dùng schema validator (JSON Schema) để kiểm tra Domain Context trước/sau mỗi process.
* Snapshot delta: engine tạo `before/after` JSON diff để audit.
* Unit tests cho process độc lập (local context test).
* Contract tests: đảm bảo process đọc/ghi đúng fields đã khai báo.
* Integration tests cho workflow.
* Versioning: mỗi domain context có field `domain.version`.

---

# 🔀 **Chương 7 - Workflow Graph — Linear, Branch, DAG, Dynamic (định nghĩa, tính chất, pattern, ví dụ)**

Workflow không chỉ là list — nó là đồ thị. POP hỗ trợ nhiều dạng, ta phân loại và nêu ngữ nghĩa.

---

## A. Linear (tuyến tính)

### Định nghĩa

Chuỗi các process thực hiện tuần tự: `p1 -> p2 -> p3 -> ...`

### Tính chất

* đơn giản, dễ hiểu
* dễ debug & trace
* phù hợp pipeline cố định

### Khi dùng

* simple ETL
* đơn nhiệm robot cycle
* demo, POC

### Ví dụ YAML

```yaml
steps:
  - vision.load_image
  - vision.detect_keypoints
  - vision.extract_features
  - classifier.classify
  - logger.log_result
```

### Pitfalls

* không linh hoạt khi cần branching; mọi logic điều kiện phải nằm trong các process hoặc chuyển sang DAG.

---

## B. Branch (rẽ nhánh, conditional)

### Định nghĩa

Tại điểm rẽ, workflow chọn nhánh dựa trên điều kiện: `p1 -> if(cond) {p2a} else {p2b} -> p3`

### Tính chất

* cho phép xử lý điều kiện
* giữ pipeline rõ ràng nếu điều kiện được mô tả ở level workflow

### Khi dùng

* feature flags
* safety checks
* xử lý lỗi (retry vs fallback)

### Ví dụ YAML (pseudo)

```yaml
steps:
  - vision.load_image
  - decision.evaluate_quality
  - branch:
      when: "ctx.quality > 0.8"
      then:
        - classifier.classify
        - publisher.publish
      else:
        - logger.log_bad_image
        - alert.operator_notify
```

### Pitfalls

* điều kiện phức tạp làm workflow khó đọc → tách thành process nhỏ kiểm tra điều kiện.

---

## C. DAG (Directed Acyclic Graph)

### Định nghĩa

Các process có phụ thuộc, có thể song song, không có vòng lặp: `p1 -> {p2,p3} -> p4` (p2 và p3 có thể chạy song song, p4 chờ cả hai).

### Tính chất

* tối ưu concurrency
* xác định dependencies rõ ràng
* cần engine hỗ trợ scheduling & merge

### Khi dùng

* heavy compute bước có thể phân tán
* preprocessing song song (feature extracts)
* pipelines có join step

### Ví dụ YAML (pseudo)

```yaml
steps:
  - stage: parallel
    branches:
      - - vision.detect_keypoints
        - vision.extract_features
      - - sensor.read_depth
        - sensor.filter_noise
  - stage: join
    wait_for: ["branch0","branch1"]
  - fusion.fuse_features
```

### Pitfalls

* merge semantics: phải định nghĩa cách join (merge strategy).
* state convergence: đảm bảo domain context sau merge coherent.

---

## D. Dynamic (runtime graph / feedback loops)

### Định nghĩa

Đồ thị có thể được xây/biến đổi runtime, có thể có feedback (vòng lặp), dynamic branching, conditional graph generation.

### Tính chất

* cực kỳ linh hoạt
* phức tạp: cần orchestration mạnh, back-pressure, idempotence, cancellation
* cần model cho timeouts, retries, compensations

### Khi dùng

* adaptive control (robot reacts to environment)
* ML online learning loop
* orchestration workflows với human-in-the-loop

### Ví dụ pseudo (YAML + runtime)

```yaml
steps:
  - capture.loop:
      until: "ctx.stop_flag == true"
      body:
        - vision.load_image
        - vision.detect_keypoints
        - evaluate_and_decide
        - branch:
            when: "ctx.need_replan"
            then:
              - planner.replan
              - executor.execute
```

### Pitfalls

* non-termination risk → require timeouts/guards
* state explosion if not pruned
* harder to test; need simulation environment

---

## Merge strategies (khi join song song/DAG)

1. **Overwrite last-writer** — branch writes take precedence by timestamp (risky).
2. **Aggregate** — collect results into array/list (good for features).
3. **Reduce** — apply a reduce function (sum/avg/merge).
4. **Custom merge function** — domain-specific deterministic merge (recommended).

---

## Engine responsibilities for graphs

* validate graph (no invalid references, cycles if not allowed)
* schedule parallel execution with locking/merge semantics
* provide snapshot & rollback for failure compensation
* support cancellation & timeout & retries
* audit trace per node (before/after)

---

# 🛠 **Chương 8 - Ngôn ngữ DSL cho POP — cú pháp, ngữ nghĩa, BNF nhỏ, ví dụ**

Mục tiêu DSL:

* dễ đọc cho cả kỹ sư & người vận hành
* đủ expressive cho linear/branch/DAG/dynamic
* có khả năng versioning & validation
* map trực tiếp tới engine

Tôi đề xuất **DSL dạng YAML** (human-friendly) với định dạng chính thức và BNF cơ bản.

---

## 3.1. Ngữ chính (core concepts)

* `workflow` — tên, metadata, version
* `steps` — danh sách các Step
* `step` có thể là:

  * `name` (string) — gọi process từ registry
  * `group` (list) — nạp group (serial hoặc parallel)
  * `branch` — condition + then/else
  * `parallel` — list of branches
  * `loop` — until/for/while style
  * `merge` — strategy
  * `transaction` — begin/commit/rollback semantics
* `inputs` / `outputs` — optional mapping per step (explicit context access)
* `on_error` — policy (retry, fallback, abort, compensate)
* `guards` — precondition checks
* `annotations` — human-readable explanation

---

## 3.2. BNF (rút gọn)

```
<workflow> ::= workflow: { name, version, metadata?, steps: <step-list> }
<step-list> ::= <step> | <step> , <step-list>
<step> ::= <call> | <group> | <branch> | <parallel> | <loop> | <transaction>
<call> ::= { call: <identifier>, inputs?: <access>, outputs?: <access>, on_error?: <policy> }
<group> ::= { group: { mode: serial|parallel, steps: <step-list> } }
<branch> ::= { branch: { when: <expr>, then: <step-list>, else?: <step-list> } }
<parallel> ::= { parallel: { branches: [<step-list>, ...], merge: <merge-strategy> } }
<loop> ::= { loop: { until: <expr> | count: <n>, body: <step-list> } }
<transaction> ::= { transaction: { steps: <step-list>, on_failure: <compensate_step_list> } }
```

---

## 3.3. Cú pháp YAML mẫu (comprehensive example)

```yaml
workflow:
  name: pick_and_place_v2
  version: 2
  metadata:
    author: "team-robot"
    created: "2025-12-08"
steps:
  - call: vision.load_image
    inputs: { read: ["global.job_id", "domain.image_id"] }
    outputs: { write: ["domain.image_bytes"] }

  - group:
      mode: parallel
      steps:
        - call: vision.detect_keypoints
          inputs: { read: ["domain.image_bytes"] }
          outputs: { write: ["domain.keypoints"] }
        - call: sensor.read_depth
          inputs: { read: ["global.job_id"] }
          outputs: { write: ["domain.depth_map"] }

  - parallel:
      branches:
        - - call: vision.extract_features
            inputs: { read: ["domain.keypoints"] }
            outputs: { write: ["domain.features"] }
        - - call: classifier.classify
            inputs: { read: ["domain.features"] }
            outputs: { write: ["domain.classification"] }
      merge:
        strategy: "custom"
        function: "fusion.merge_classif_and_features"

  - branch:
      when: "ctx.classification.confidence > 0.85"
      then:
        - call: planner.plan_pick
        - call: executor.execute_pick
      else:
        - call: logger.log_low_confidence
        - call: operator.request_human_intervention

  - transaction:
      steps:
        - call: db.save_pick_entry
      on_failure:
        - call: db.compensate_save
```

---

## 3.4. Ngữ nghĩa chi tiết

* `call` — tên process phải có trong registry; engine sẽ `fn(ctx, env)`.
* `inputs` / `outputs` — khai báo explicit; engine validate trước khi chạy.
* `group.mode=parallel` — engine sẽ spawn branches (thread/process) và merge theo strategy.
* `parallel.merge.strategy` — có thể `aggregate`, `reduce`, `custom`.
* `branch.when` — expression evaluated against `ctx` snapshot; DSL engine must provide a safe expression evaluator (no arbitrary code).
* `transaction` — bắt đầu transaction semantic: nếu any step fails, engine chạy `on_failure` list (compensation).
* `on_error` per call — `retry: {times: n, backoff: ms}`, `fallback: call_name`, `abort: true`.

---

## 3.5. Validation rules (engine checks)

1. All `call` names exist in registry.
2. `inputs` fields exist in current schema or are allowed optional.
3. `outputs` must not overwrite Global Context.
4. `merge` function present if custom.
5. `branch.when` expression safe & deterministic.
6. `transaction.on_failure` steps valid.

---

## 3.6. Error handling & compensation

* Prefer **compensating transactions** over auto-rollback for side-effects (PLC commands).
* `transaction` block defines compensation steps explicitly.
* `on_error` policy per step: `retry`, `fallback`, `skip`, `abort`.

---

## 3.7. Serialization & versioning

* DSL files have `version` field.
* Changes in workflow structure should bump `workflow.version`.
* Engine keeps history of executed workflow versions for audit.

---

## 3.8. Mapping DSL → Engine

Engine responsibilities:

1. parse YAML → AST
2. validate AST against registry & schemas
3. compile AST to execution plan (linearize where possible)
4. execute with context snapshots, per-step logs
5. manage parallelism, merges, transactions
6. provide metrics, tracing, observability

---

## 3.9. Tooling & UX suggestions

* **Visual editor**: node-based flow editor that produces DSL YAML.
* **Linting**: static analyzer to enforce POP rules (explicit inputs/outputs, no global writes).
* **Simulator**: dry-run mode with fake env to validate logic.
* **Live debugger**: step-through with snapshots.
* **Schema explorer**: show domain context schema and versions.

---

## ✅ Kết luận ngắn gọn (hành động)

* Tổ chức code: **module-based**, `registry`, `engine`, `adapters`, `workflows` (YAML).
* Workflow types: Linear / Branch / DAG / Dynamic — engine phải hỗ trợ cả 4; dùng merge strategies, transactions, compensation.
* DSL: YAML-first, rõ ràng, with `call`, `group`, `branch`, `parallel`, `loop`, `transaction` — có validation & versioning.

---

# **Chương 9 - Cách xử lý Adapter Layer trong POP**

---

## 🟦 **1. Trước hết: POP *không xem Adapter là tầng* như Clean Architecture**

Trong Clean Architecture:

* Adapter là một “Layer”
* Domain → Use-case → Interface → Adapter → Framework

Trong POP:

**Process là trung tâm**,
**Context là dòng chảy**,
do đó Adapter KHÔNG thể trở thành một tầng riêng tách biệt theo kiểu onion.

POP cần đơn giản hơn, tường minh hơn và phù hợp với mô hình dòng chảy hơn.

---

## 🟩 **2. Adapter trong POP là gì?**

**Adapter = cổng giao tiếp giữa process và thế giới bên ngoài.**

Bao gồm:

* I/O thiết bị (camera, PLC, robot, cảm biến)
* Database / file / network
* API bên ngoài
* Các dịch vụ hoặc framework không thuộc core logic

**Adapter chỉ làm 2 việc:**

1. **Chuẩn hóa dữ liệu vào/ra của thiết bị bên ngoài**
2. **Không để logic bên ngoài xâm nhập vào process**

---

## 🟧 **3. Nguyên tắc đầu tiên: Process KHÔNG được gọi trực tiếp thiết bị hoặc API**

Đây là điểm POP *học từ Clean Architecture*, nhưng điều chỉnh theo triết lý của POP.

**Sai với POP:**

```python
def xu_ly():
    frame = camera.read()
    db.save(result)
```

**Đúng theo POP:**

```python
def xu_ly(ctx, env):
    frame = env.camera.read()
    env.db.write(result)
```

Bạn thấy:

* POP không tạo interface class, không tạo 10 lớp abstraction như OOP
* POP chỉ yêu cầu: Process chỉ giao tiếp qua một **env (environment adapter)** đơn giản, tường minh

---

## 🟦 **4. Adapter trong POP phải tuân thủ 4 quy tắc**

### **Quy tắc 1 — Adapter không chứa logic xử lý**

Adapter chỉ chuyển đổi:

* raw data → context field
* context field → tín hiệu/command ra ngoài

**Không làm logic, không quyết định, không nhảy nhánh.**

---

### **Quy tắc 2 — Adapter không trả về context**

Adapter chỉ trả về:

* dữ liệu đơn vị (string, number, frame)
* hoặc trạng thái (success, fail)

**Process mới là nơi trả về context.**

---

### **Quy tắc 3 — Adapter tách biệt theo domain tài nguyên**

Ví dụ cấu trúc:

```
adapters/
    camera/
        opencv_adapter.py
        realsense_adapter.py
    plc/
        siemens_adapter.py
        mitsubishi_adapter.py
    robot/
        nachi_adapter.py
    storage/
        file_adapter.py
        sqlite_adapter.py
```

Mỗi loại tài nguyên nằm trong một namespace riêng → không lẫn lộn.

---

### **Quy tắc 4 — Quá trình tương tác bên ngoài phải được mô tả tường minh trong process**

Process phải thể hiện hết luồng:

* lấy camera
* đọc hình
* chuẩn hóa dữ liệu
* ghi vào context

**Không giấu bên trong abstraction.**

---

## 🟦 **5. Adapter trong POP không bao giờ dùng interface OOP**

POP không khuyến khích OOP trong những tác vụ phức tạp, vì vậy:

* Không dùng interface class
* Không dùng abstract base class
* Không dùng DI framework
* Không dùng inversion of control container

Thay vào đó, POP dùng mô hình **Context + Env + Process**:

```
ctx → process → ctx
process gọi env để tương tác bên ngoài
```

Cực kỳ rõ ràng, cực kỳ đơn giản.

---

## 🟩 **6. Cấu trúc Adapter trong POP (gợi ý chuẩn)**

```
/core
    /process
    /context
    /rules

/env
    camera.py
    plc.py
    robot.py
    database.py
    filesystem.py
```

* **core** không biết gì về thiết bị
* **env** không chứa logic—chỉ thao tác thiết bị
* **process** chỉ gọi env theo đúng tên

---

## 🟦 **7. Ví dụ thực tế (mang tính POP thuần)**

### **Adapter: camera.py**

```python
class Camera:
    def read(self):
        frame = ... # đọc từ OpenCV
        return frame
```

Không OOP phức tạp, không interface.

---

### **Process: tim_vat**

```python
def tim_vat(ctx, env):
    frame = env.camera.read()
    ctx.anh.frame = frame
    ctx.anh.vat = detect(frame)
    return ctx
```

Cực kỳ rõ ràng:

* process làm logic
* adapter chỉ cung cấp dữ liệu gốc

---

## 🟩 **8. Tóm tắt — Adapter trong POP nên như sau**

| Yếu tố         | POP yêu cầu                                     |
| -------------- | ----------------------------------------------- |
| Vai trò        | Gateway để process giao tiếp với thế giới ngoài |
| Mục tiêu       | Cách ly logic khỏi phụ thuộc thiết bị           |
| Không được làm | Logic, nhảy nhánh, xử lý context                |
| Cách gọi       | env.resource.method()                           |
| Abstraction    | Mỏng, đơn giản, không OOP                       |
| Tổ chức        | theo domain tài nguyên                          |
| Flow           | tường minh trong process, không giấu            |

---

## 🟥 **9. ĐIỀU SỐNG CÒN:

POP không biến Adapter thành một layer kiến trúc tĩnh như Clean Architecture.**

Trong Clean Architecture:

* Adapter là cả một tầng
* số lượng abstraction nhiều
* interface-infrastructure pattern phức tạp

Trong POP:

* Adapter chỉ là “đường ống” (port)
* cực mỏng
* không can thiệp vào context
* không áp đặt abstract layer
* không biến thành cấu trúc vòng tròn

**POP giữ linh hồn: process là trung tâm, context là dòng chảy.**

---

# **Chương 10 -  Process I/O Contract Specification**

---

## 🟥 **POP SPEC 1.0 — PROCESS I/O CONTRACT**

**Tài liệu này mô tả chuẩn về cách một Process trong POP định nghĩa, đọc, ghi và biến đổi dữ liệu.**
Contract đảm bảo:

* tính an toàn
* tính tường minh
* tính kiểm soát
* không nhảy nhánh bất ngờ
* không phá vỡ dòng chảy context
* dễ kiểm tra, dễ bảo trì

POP không sử dụng Interface, không dùng class trừu tượng, không dùng OOP phức tạp.
Contract này thuần túy là **định nghĩa hành vi và dữ liệu** của một Process.

---

## 🟥 **1. MỤC TIÊU CỦA I/O CONTRACT**

1. Đảm bảo mỗi Process có **đầu vào rõ ràng** (input fields).
2. Đảm bảo mỗi Process chỉ **ghi đúng các phần được phép** của context (output fields).
3. Ngăn chặn Process tác động nhầm hoặc phá hỏng phần context ngoài phạm vi.
4. Đảm bảo Flow Engine và người đọc code hiểu đúng điều kiện tiền đề và kết quả.
5. Làm cho việc test, refactor và audit dễ dàng và an toàn hơn.
6. Giảm lỗi runtime do thiếu trường dữ liệu, sai kiểu, hoặc ghi sai chỗ.

---

## 🟥 **2. ĐỊNH NGHĨA PROCESS I/O CONTRACT**

Mỗi Process phải khai báo rõ:

1. **Input Contract** — phần context cần để chạy
2. **Output Contract** — phần context Process sẽ ghi hoặc thay đổi
3. **Side-effect Contract** — những tương tác bên ngoài (nếu có)
4. **Error Contract** — Process có thể trả lại lỗi gì và trong điều kiện nào

Không khai báo → không được phép đọc/ghi.

---

## 🟥 **3. CẤU TRÚC CONTRACT CHUẨN**

```
process <tên process>:
    input:
      - <context_path>: <loại dữ liệu yêu cầu>
      - ...
    output:
      - <context_path>: <loại dữ liệu ghi>
      - ...
    side_effect:
      - <tên tài nguyên ngoài>: <hành động>
      - ...
    error:
      - <mã lỗi>: <điều kiện gây lỗi>
```

Toàn bộ đều là **khai báo**, không phải code.

---

## 🟥 **4. QUY TẮC INPUT CONTRACT**

### **Input Rule 1 — Process phải khai báo tất cả dữ liệu nó cần.**

Process không được đọc bất kỳ phần nào của context không nằm trong input contract.

### **Input Rule 2 — Input phải tồn tại trước khi Process được chạy**

Flow Engine phải kiểm tra:

* input tồn tại
* đúng kiểu
* đúng phạm vi

Nếu không đủ → Process không được chạy.

### **Input Rule 3 — Không được biến đổi input**

Input context là **hạng mục đọc**, không được mutate.

---

## 🟥 **5. QUY TẮC OUTPUT CONTRACT**

### **Output Rule 1 — Process chỉ được ghi vào đúng phần output đã khai báo**

Không được ghi lung tung sang các phần context khác.

### **Output Rule 2 — Output phải đủ ngữ nghĩa**

Ghi đúng:

* dạng dữ liệu
* ý nghĩa dữ liệu
* vị trí dữ liệu

### **Output Rule 3 — Nếu không có output → explicit: []**

Process không ghi gì cũng phải khai báo rõ:

```
output: []
```

---

## 🟥 **6. QUY TẮC SIDE-EFFECT CONTRACT**

Side-effect bao gồm:

* đọc camera
* gửi lệnh robot
* ghi DB
* gửi gói TCP
* đọc file

### **Side-effect Rule 1 — Process phải khai báo đầy đủ tất cả side-effect**

### **Side-effect Rule 2 — Process chỉ được sử dụng Adapter qua env**

Không được tự thao tác thiết bị trực tiếp.

### **Side-effect Rule 3 — Không giấu side-effect trong nội bộ logic**

Nếu có:

* retry
* waiting
* timeout
* giao thức handshake

→ đều phải miêu tả trong contract hoặc tài liệu kèm theo.

---

## 🟥 **7. QUY TẮC ERROR CONTRACT**

Cấu trúc:

```
error:
  - "khong_tim_thay_du_lieu": "ctx.anh.frame is None"
  - "robot_ban_ngoai_pham_vi": "tinh_toan_toa_do out_of_range"
```

### **Error Rule 1 — Tất cả lỗi có thể xảy ra phải được khai báo**

### **Error Rule 2 — Điều kiện lỗi phải xác định được từ input hoặc side-effect**

### **Error Rule 3 — Process không được raise lỗi chưa khai báo**

---

## 🟥 **8. VÍ DỤ HOÀN CHỈNH**

### Process: tìm vật trong ảnh

```
process tim_vat:
    input:
      - anh.frame: Image
    output:
      - anh.vat: ObjectData | None
    side_effect: []
    error:
      - "frame_trong": "anh.frame == None"
```

### Process: đọc camera

```
process doc_camera:
    input: []
    output:
      - anh.frame: Image
    side_effect:
      - camera: "read"
    error:
      - "camera_loi": "camera.read thất bại"
```

### Process: gửi lệnh robot

```
process robot_gap:
    input:
      - robot.toa_do: Point3D
    output:
      - robot.trang_thai: State
    side_effect:
      - plc: "send command"
    error:
      - "toa_do_khong_hop_le": "robot.toa_do out_of_range"
```

---

## 🟥 **9. QUY TẮC KHI KẾT HỢP CÁC PROCESS TRONG WORKFLOW**

1. **Output của process A phải khớp input của process B**
2. Engine phải kiểm tra và đảm bảo contract hợp lệ
3. Một process không được phụ thuộc vào output mà nó không khai báo
4. Khi context tiến hóa → contract phải được cập nhật tương ứng

---

## 🟥 **10. POP ENGINE: CÁCH ÁP DỤNG CONTRACT**

Engine cần thực hiện:

1. Validate input
2. Locked write vùng output
3. Validate side-effect xảy ra đúng như contract
4. Validate không có ghi vượt ngoài phạm vi
5. Bắt lỗi theo đúng error contract
6. Ghi output vào context mới

Điều này đảm bảo POP đạt:

* tính an toàn
* tính dự đoán
* tính tường minh
* tính kiểm soát mạnh

---

## 🟥 **11. TÍNH CHẤT THEN CHỐT: CONTRACT KHÔNG PHẢI LÀ OOP**

* Không interface
* Không abstract class
* Không DI container
* Không hàm ảo
* Không inversion of control

POP dùng:

* file khai báo
* cấu trúc dữ liệu tĩnh
* rule thuần logic
* kiểm soát runtime bằng context + engine

Vẫn tường minh tuyệt đối.

---

## 🟥 **12. LỢI ÍCH CỤ THỂ KHI CÓ PROCESS I/O CONTRACT**

* Mapping context → process chính xác
* Giảm 90% lỗi do đọc/ghi sai context
* Dễ test đơn vị
* Dễ audit
* Dễ tracking tiến hóa dữ liệu
* Dễ xác định phạm vi ảnh hưởng khi refactor
* Dễ sinh lược đồ tự động
* Dễ tạo UI/Graph editor tự động từ contract

Contract là "xương sống" giúp POP trở thành kiến trúc hoàn chỉnh và mạnh mẽ.

---

# **Chương 11 – Mô hình Đồng thời và Hiệu năng trong POP**

---

## 🟥 **1. Mục tiêu và vấn đề POP phải giải quyết**

Mô hình Concurrency & Performance của POP nhắm giải quyết **hai tử huyệt** của bất kỳ kiến trúc quy trình (process-oriented architecture):

1. **An toàn đồng thời (Concurrency Safety)**
   – tránh tình trạng đọc/ghi hỗn loạn (race condition), tránh ghi chồng, mất dữ liệu.

2. **Hiệu năng (Performance)**
   – cho phép xử lý song song, giảm chi phí copy, tận dụng đa lõi, không đánh đổi tính minh bạch.

Ba yêu cầu bất biến:

* **Safety > Clarity > Performance**
* Process phải tường minh, không che giấu logic đồng thời.
* Engine phải chịu trách nhiệm bảo vệ Context, không đẩy gánh nặng lên dev.

---

## 🟥 **2. Triết lý Phi-Nhị-Nguyên về Concurrency**

POP không áp đặt “một mô hình tối ưu cho mọi thứ”.
Mỗi nền tảng, mỗi domain có đặc thù khác nhau:

* Python bị giới hạn bởi GIL.
* Rust/C++ hỗ trợ ownership.
* Hệ phân tán cần Actor.

Do đó POP xây dựng **Phổ Concurrency 3 Cấp (Three-Level Concurrency Spectrum)**, cho phép hệ thống tiến hóa theo nhu cầu:

**Cấp 1 — Mượn tài nguyên (Borrowing)**
**Cấp 2 — Gộp Sai biệt (Delta Aggregation)**
**Cấp 3 — Sharding/Actor Phân tán**

Không phải “chọn một trong ba”, mà là ba lớp có thể phối hợp linh hoạt.

---

## 🟥 **3. Nguyên tắc Cốt lõi: Bất biến Cục bộ (Local Immutability)**

Tất cả Process trong POP hoạt động trên **Snapshot cục bộ**, không bao giờ ghi trực tiếp vào Context gốc.

Điều này bảo đảm:

* Tránh race condition ngay từ triết lý thiết kế.
* Giữ quá trình xử lý tường minh.
* Cho phép kiểm tra và audit.

Mọi thay đổi phải trả về **Delta** hoặc **Context mới**.

---

## 🟥 **4. Cấp 1 — Mượn Tài nguyên theo Contract (Borrowing Model)**

**Phù hợp:** Rust, C++, hệ thống cần realtime và hiệu năng cao.

### **Cơ chế**

1. Process khai báo **Read Set / Write Set**.
2. Engine kiểm tra:

   * Nhiều process có thể **đọc chung** một Shard.
   * Chỉ 1 process được **ghi độc quyền** vào Shard đó tại thời điểm bất kỳ.
3. Nếu Write conflict → process sau phải chờ hoặc bị từ chối.

### **Ưu điểm**

* Tránh race ở mức tuyệt đối.
* Hiệu năng cao (nếu ngôn ngữ hỗ trợ).
* Luồng logic dễ dự đoán.

### **Hạn chế / Câu hỏi buộc phải trả lời**

* **Lifetime** của borrow kéo dài bao lâu?
* **Deadlock** xử lý thế nào?
* Có **quy tắc thứ tự mượn shard** để tránh nghẽn không?
* Nếu contract sai → hệ thống phát hiện thế nào?

### **Giả định nền tảng**

* Process phải khai báo chính xác read/write.
* Shard phải được phân tách hợp lý.
* Team có công cụ kiểm chứng (linter/validator).

---

## 🟥 **5. Cấp 2 — Gộp Sai biệt (Delta Aggregation Model)**

**Phù hợp:** Python, JavaScript, JVM, môi trường scripting.

### **Cơ chế**

1. Process chạy song song chỉ sinh ra **Delta** (bản ghi thay đổi).
2. Engine thu thập tất cả Delta.
3. Engine thực hiện **Merge** vào Context một lần duy nhất.

### **Ưu điểm**

* Không dùng lock.
* Dễ đọc, dễ debug.
* Phù hợp môi trường linh hoạt.

### **Hạn chế / Câu hỏi quan trọng**

* **Merge Policy** cho từng loại field là gì?
* Nếu xung đột → retry hay reject?
* Delta có thể quá lớn → memory bloat?
* Nếu merge thất bại → rollback hay dùng phiên bản bị lỗi?

### **Giả định nền tảng**

* Domain có semantics rõ ràng cho merge.
* Conflict rate thấp hoặc merge logic đơn giản.
* Delta nhỏ (nếu GUI hoặc sensor stream → Delta có thể rất lớn).

---

## 🟥 **6. Cấp 3 — Phân mảnh theo Actor (Sharded Actor Model)**

**Phù hợp:** Microservice, Robotics phức hợp, Distributed Systems.

### **Cơ chế**

1. Context chia thành các **Shard độc lập**.
2. Mỗi Shard thuộc về một Actor.
3. Process gửi message thay vì ghi chung bộ nhớ.

### **Ưu điểm**

* Không có shared memory → không có race.
* Scale tốt theo chiều ngang.

### **Hạn chế / Câu hỏi bắt buộc**

* **Độ trễ** truyền message chấp nhận được không?
* **Consistency model** gì? (eventual / strong?)
* **Retry** có tạo ra duplicate-effect?
* Shard key có hợp lý không? (nếu shard quá lớn → Actor bị nghẽn)

### **Giả định**

* Hệ thống có kiến thức distributed system.
* Network ổn định.
* Shard boundaries tự nhiên trong domain.

---

## 🟥 **7. Chiến lược Tối ưu Hiệu năng**

POP hỗ trợ 2 chiến lược giảm chi phí tạo Context phiên bản mới.

---

### **7.1 Copy-on-Write (Sao chép khi ghi)**

* Khi đọc → không copy.
* Khi ghi → chỉ copy phần cần thay đổi.

**Câu hỏi/phản biện quan trọng:**

* Chi phí shallow copy của ngôn ngữ hiện tại có rẻ không?
* Có leak reference không?
* Nếu context lồng nhau nhiều cấp → độ sâu copy thế nào?

---

### **7.2 Persistent Data Structures (Cấu trúc dữ liệu bền vững)**

* Dùng structural sharing để giảm copy.
* Tạo context mới gần như O(1).

**Phản biện:**

* GC của ngôn ngữ có hỗ trợ tốt không?
* Có gây cache-miss nhiều hơn không?
* Trên Python: đây không phải giải pháp tự nhiên.

---

## 🟥 **8. Yêu cầu Thu thập Dữ liệu (Data Required for Decision)**

Để chọn chiến lược phù hợp, cần có dữ liệu thực:

* Tần suất đọc/ghi của từng shard.
* Kích thước trung bình của Delta.
* Tỉ lệ conflict thực tế.
* Độ trễ I/O.
* Số lượng Process chạy song song.
* CPU core count, cache behavior.
* Ngôn ngữ và GC profile.

**Nếu không có dữ liệu:**
→ lựa chọn concurrency sẽ mang tính may rủi.

---

## 🟥 **9. Giả định cốt lõi của POP Concurrency Model**

1. Process luôn khai báo đúng contract (cần tooling hỗ trợ).
2. Context được chia thành Shard hợp lý.
3. Merge policies có thể định nghĩa rõ.
4. Domain cho phép retry hoặc reject.
5. Team có năng lực thực thi Engine.
6. Delta không quá lớn và không phát nổ về memory.
7. Shard không trở thành “điểm nghẽn độc quyền”.

**Nếu bất kỳ giả định nào sai:**
→ concurrency model có thể thất bại.

---

## 🟥 **10. Suy luận tổng thể và Tác động**

**Suy luận logic của mô hình:**

* Tách context → giảm tranh chấp.
* Bất biến cục bộ → tránh race.
* Delta & Merge → chia tách trách nhiệm.
* Persistent structure → giảm chi phí copy.
* Actor → scale theo chiều ngang.

**Tác động nếu áp dụng:**

* Hệ thống POP có thể mở rộng và chạy song song an toàn.
* Engine trở nên phức tạp hơn.
* Yêu cầu người thiết kế phải cẩn trọng với Shard, Contract và Merge.

**Nếu không áp dụng:**

* POP đơn giản hơn nhưng chỉ chạy tốt ở mô hình tuần tự, không scale.

---

## 🟥 **11. Kết luận của Chương 11**

Mô hình đồng thời & hiệu năng của POP không đi theo một mô hình duy nhất mà dựa trên **phổ linh hoạt 3 cấp**, mỗi cấp phù hợp với môi trường và quy mô khác nhau.

Mô hình này vừa giữ được:

* **sự tường minh** của POP,
* **tính an toàn** trong xử lý dữ liệu,
* **khả năng mở rộng** khi hệ thống lớn dần.

Đồng thời, Chương 11 cũng nêu rõ:

* giới hạn,
* rủi ro,
* các giả định nền tảng,
* các câu hỏi phải được trả lời,
* và dữ liệu cần thu thập trước khi triển khai thực tế.

**POP không tránh né phức tạp — POP định vị lại phức tạp cho đúng chỗ: đưa vào Engine, tránh đưa vào đầu lập trình viên.**

---


# **Chương 12 – Cộng sinh Đa mô hình: POP, OOP và Clean Architecture**

---

## 🟥 **1. Định vị POP trong bối cảnh Đa mô hình**

POP không sinh ra để tiêu diệt OOP hay thay thế Clean Architecture.
POP sinh ra để giải quyết bài toán mà hai mô hình kia gặp khó khăn: **Quản lý sự phức tạp của Dòng chảy (Flow Complexity).**

Để xây dựng một hệ thống hoàn chỉnh, chúng ta cần cái nhìn đa chiều:

1.  **OOP** cực mạnh trong việc đóng gói trạng thái vật lý (UI, Device Driver).
2.  **Clean Architecture** cực mạnh trong việc thiết lập ranh giới bảo vệ (Enterprise Boundaries).
3.  **POP** cực mạnh trong việc điều phối logic nghiệp vụ (Orchestration).

Một kiến trúc sư giỏi là người biết dùng đúng công cụ cho đúng tầng của hệ thống.

---

## 🟦 **2. Quy tắc Phối hợp 1: Dòng chảy & Cấu phần (POP + OOP)**

Quy tắc phân định ranh giới giữa POP và OOP dựa trên tính chất của đối tượng xử lý:

### **Lãnh địa của OOP (Component & State)**
Dùng OOP khi bạn cần mô hình hóa một thực thể có **trạng thái nội tại bất biến** hoặc **gắn liền với phần cứng/giao diện**.
*   **UI Widget:** `Button`, `Window` (gắn liền input chuột/phím với trạng thái hiển thị).
*   **Device Driver:** `CameraDevice`, `SerialPort` (quản lý buffer, lock, connection handle).

### **Lãnh địa của POP (Flow & Transformation)**
Dùng POP khi bạn cần mô tả **logic nghiệp vụ** hoặc **sự biến đổi dữ liệu**.
*   **Logic:** "Nếu thấy vật cản thì dừng lại" → Đây là Process.
*   **Data:** Ảnh từ Camera, Tọa độ Robot → Đây là Context.

> **Mô hình Cộng sinh:**
> **Process (POP)** đóng vai trò "Nhạc trưởng", điều phối các **Object (OOP)** thực thi nhiệm vụ cụ thể thông qua Adapter.
>
> *Ví dụ:* Process `scan_environment` (POP) gọi phương thức `robot_driver.move_to()` (OOP).

---

## 🟩 **3. Quy tắc Phối hợp 2: Thang đo Trừu tượng (POP + Clean Architecture)**

Clean Architecture (CA) bảo vệ hệ thống bằng các lớp Interface dày đặc (Dependency Inversion). POP tôn trọng điều này nhưng đề xuất một **Thang đo linh hoạt (Abstraction Scale)** tùy theo quy mô dự án.

### **Level 1: Duck Typing (Dynamic Link)**
*   **Phù hợp:** Startups, Prototype, Script xử lý dữ liệu, Game Logic.
*   **Cấu trúc:** `env` là object tự do. Process gọi `env.camera.read()` mà không cần interface định trước.
*   **Ưu điểm:** Tốc độ phát triển cực nhanh, code gọn nhẹ.

### **Level 2: Strict Typing (Static Contract)**
*   **Phù hợp:** Sản phẩm thương mại, Hệ thống nhúng an toàn (Safety-critical).
*   **Cấu trúc:** Sử dụng Python `Protocol` hoặc Rust `Trait` để định nghĩa `EnvContract`. Process chỉ nhìn thấy Contract.
*   **Ưu điểm:** IDE hỗ trợ tốt, đảm bảo thay thế Adapter an toàn.

### **Level 3: Enterprise Injection (Hard Boundaries)**
*   **Phù hợp:** Hệ thống Core Banking, Super-App hàng trăm module.
*   **Cấu trúc:** Áp dụng Clean Architecture triệt để. `Env` được inject qua DI Container. Mọi I/O đều qua Interface nghiêm ngặt.
*   **Ưu điểm:** Module hóa tuyệt đối, team 100 người không dẫm chân nhau.

---

## 🟥 **4. Tuyên ngôn Kiến trúc Hợp nhất (Unified Architecture)**

Thay vì tư duy nhị nguyên "POP hay là chết", Manifesto khẳng định:

**POP là Kiến trúc Vĩ mô (Macro-Architecture)**
Nó định hình xương sống của ứng dụng là các dòng chảy dữ liệu minh bạch.

**OOP & Functional là Kiến trúc Vi mô (Micro-Architecture)**
Chúng là công cụ để chế tạo nên các "viên gạch" (Adapter, Util) chất lượng cao nhất.

**Clean Architecture là Hệ thống Phòng thủ**
Nó được kích hoạt khi độ phức tạp của dự án chạm ngưỡng cần kiểm soát rủi ro con người.

Sự kết hợp này tạo ra một hệ thống: **Minh bạch ở tổng thể, Mạnh mẽ ở chi tiết, và Bền vững theo thời gian.**
