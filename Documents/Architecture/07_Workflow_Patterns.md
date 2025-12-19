# Chương 7: Mô hình Workflow & Ngôn ngữ Spec (Theus Flow)

---

## 7.1. Workflow là một "Playlist", không phải Code

Trong Theus, file `specs/workflow.yaml` không phải là nơi bạn lập trình. Nó là nơi bạn **kê khai thứ tự**.

Hãy tưởng tượng bạn là DJ. Các bài hát (Process) đã được thu âm sẵn. Nhiệm vụ của bạn là sắp xếp chúng thành một danh sách phát (Playlist) hợp lý.

**Tại sao Theus giới hạn sức mạnh của Workflow YAML?**
> Bởi vì chúng tôi đã thấy quá nhiều hệ thống "No-Code" biến thành ác mộng khi người dùng cố gắng viết vòng lặp `for`, biến `if/else`, và xử lý exception ngay trong file YAML/XML.

Theus giữ cho YAML "ngu" (Dumb) để hệ thống đơn giản (Robust).

---

## 7.2. Cấu trúc chuẩn của `workflow.yaml`

File cấu hình này kiểm soát toàn bộ vòng đời của ứng dụng.

```yaml
version: "2.0"
name: "Robot Delivery Application"

# [1] Định nghĩa các chế độ chạy
modes:
  production:
    steps:
      - "vision.localize"      # Step 1: Định vị
      - "nav.plan_path"        # Step 2: Lập kế hoạch
      - "nav.execute_move"     # Step 3: Di chuyển
      
  simulation:
    steps:
      - "sim.load_mock_map"    # Load map giả
      - "nav.plan_path"        # (Tái sử dụng logic thật)
      - "sim.mock_move"        # Di chuyển ảo
      
# [2] Cấu hình Runtime
settings:
  timeout_ms: 5000       # Timeout cho mỗi step
  stop_on_error: true    # Gặp lỗi là dừng ngay
```

---

## 7.3. Pattern: Theus Orchestrator (Nhạc trưởng)

Bạn sẽ hỏi: *"Nếu YAML chỉ chạy tuần tự, thì làm sao tôi xử lý logic rẽ nhánh phức tạp (Cấu trúc If/Else, Loop)?"*

Câu trả lời: **Hãy dùng code Python để làm Nhạc trưởng.**

Chúng ta tạo ra một Process đặc biệt, gọi là **Orchestrator**.

### Ví dụ: Xử lý rẽ nhánh "Nếu thấy người thì chào, không thì đi tiếp"

**1. Trong `workflow.yaml` (Vẫn tuyến tính):**
```yaml
steps:
  - "vision.detect_human"
  - "behavior.decide_action"  <-- Orchestrator
  - "behavior.execute_action"
```

**2. Trong `src/domain/behavior.py`:**
```python
@process(
    inputs=["domain.vision.has_human"], 
    outputs=["domain.cmd.next_action"]
)
def decide_action(ctx):
    # Logic rẽ nhánh nằm ở đây (Nơi nó thuộc về)
    if ctx.domain.vision.has_human:
        ctx.domain.cmd.next_action = "GREET"
    else:
        ctx.domain.cmd.next_action = "MOVE"
```

> **Triết lý:** Đừng đưa Logic "If/Else" lên file cấu hình. Hãy để nó trong Code. File cấu hình chỉ nên chứa "Dòng chảy cấp cao".

---

## 7.4. Các trường hợp sử dụng nâng cao

### A. Dynamic Loop (Vòng lặp động)
Nếu bạn muốn robot lặp lại hành động gắp đồ cho đến khi hết đồ?
*   **Không dùng:** `while` trong YAML.
*   **Hãy dùng:** Cơ chế `Engine.loop()` ở tầng ứng dụng hoặc một Process trả về trạng thái `CONTINUE`.

### B. Parallel Execution (Chạy song song)
Hiện tại Theus chủ trương **Single Threaded by Default** để đảm bảo an toàn tuyệt đối.
Tuy nhiên, bên trong một Process, bạn hoàn toàn có thể dùng `concurrent.futures` để download 10 ảnh cùng lúc, miễn là bạn đợi chúng xong (join) trước khi trả lại Context.

---

## 7.5. Kết luận
*   **Workflow YAML:** Dùng để nhìn tổng quan (Big Picture).
*   **Python Process:** Dùng để xử lý chi tiết (Nitty Gritty).

Sự phân chia này giúp người quản lý (Manager) có thể đọc hiểu Workflow mà không cần biết code, trong khi Developer có toàn quyền sức mạnh của Python để xử lý logic phức tạp.
