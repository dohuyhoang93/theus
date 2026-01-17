# Đánh giá Tính Khả thi Kỹ thuật (Technical Feasibility) - Theus V2.1

## 1. Đánh giá Độ phức tạp (Complexity Analysis)
**Mức độ: CAO (High)**

*   **Logic Điều phối (FSM):** Trung bình (Medium).
    *   Việc parse YAML thành Graph là bài toán cơ bản.
    *   Thách thức: Xử lý các vòng lặp (Cycles) và chuyển tiếp có điều kiện phức tạp.
*   **Bất đồng bộ (Concurrency):** Rất cao (Very High).
    *   Đây là phần khó nhất. Python có GIL (Global Interpreter Lock). Dùng `threading` hay `asyncio` đều có điểm đau:
        *   `threading`: Dễ deadlock, khó debug state.
        *   `asyncio`: "Lây nhiễm" (Viral) - toàn bộ code phải là async/await. Nếu Process của user là sync (chặn), nó sẽ block cả loop asyncio.
    *   **Quyết định:** Nên dùng `ThreadPoolExecutor` để bọc các Process sync của User.

## 2. Rủi ro Tiềm ẩn (Risks)
1.  **Deadlock (Khóa chết):**
    *   *Kịch bản:* Process A giữ Lock Domain, chờ Signal từ Process B. Process B cần Lock Domain để chạy -> Deadlock.
    *   *Mitigation:* Lock Timeout và phát hiện Cycle Deadlock.
2.  **State Inconsistency (Dữ liệu không nhất quán):**
    *   *Kịch bản:* UI đọc dữ liệu trong khi Process đang ghi dở dang (Dirty Read).
    *   *Mitigation:* Dùng `ContextGuard` với Read/Write Lock nghiêm ngặt.
3.  **Non-Determinism (Không xác định):**
    *   Thứ tự chạy thread không cố định -> Bug "Heisenbug" (Lỗi biến mất khi debug).

## 3. Chiến lược Kiểm thử (Test Strategy)
Cần bổ sung các loại test mới ngoài Unit Test:

*   **Deadlock Torture Test:**
    *   Chạy 100 process song song tranh chấp 1 resource.
    *   Assert: Không treo (Timeout xử lý đúng).
*   **Race Detector:**
    *   Dùng công cụ `tsan` (ThreadSanitizer) hoặc logic check sum dữ liệu sau khi chạy song song.
*   **Determinism Mock:**
    *   Inject `FakeScheduler` để control thứ tự chạy thread chính xác trong khi test, giúp tái hiện bug.

## 4. Chi phí Runtime (Runtime Overhead)
*   **Memory:**
    *   `ThreadPool`: Mỗi thread tốn ~8MB stack (mặc định OS). Với 100 Process -> 800MB RAM.
    *   *Tối ưu:* Dùng `Action Queue` với số lượng Thread cố định (ví dụ: `max_workers=4`).
*   **Latency:**
    *   Lock Acquisition: Tốn micro-seconds. Chấp nhận được.
    *   Context Marshaling: Nếu dùng `multiprocessing` (Process riêng) thì tốn chi phí serialize (pickle). Dùng `threading` thì rẻ (share memory).

## TỔNG KẾT
Phương án dùng **Microkernel + ThreadPool** là khả thi và cân bằng nhất cho Theus. Nó tránh việc bắt user viết code `async/await` phức tạp, nhưng vẫn tận dụng được đa nhân CPU (cho IO bound) và giữ GUI mượt mà.

## 5. Giải thích lựa chọn ThreadPoolExecutor

Tại sao `ThreadPoolExecutor` (TPE) lại an toàn hơn `threading.Thread` trần (raw threads) hoặc `asyncio`?

**A. Kiểm soát Tài nguyên (Resource Bounding):**
*   **Vấn đề:** Nếu dùng `threading.Thread(target=process).start()`, khi có 1000 event click -> Hệ điều hành tạo 1000 threads -> Crash OS (Out of Memory/Process Limit).
*   **Giải pháp TPE:** Ta set `max_workers=4`. Nếu có 1000 việc, TPE chỉ chạy 4 thread cùng lúc, 996 việc còn lại nằm trong Queue chờ. **Hệ thống không bao giờ bị quá tải.**

**B. Tương thích Code Cũ (Backward Compatibility):**
*   **Vấn đề:** `asyncio` đòi hỏi hàm phải có từ khóa `async def` và `await`. Để dùng `asyncio`, ta phải viết lại toàn bộ thư viện Theus và code của User.
*   **Giải pháp TPE:** TPE chạy được hàm chuẩn `def process(ctx)`. Code cũ chạy tốt mà không cần sửa đổi gì.

**C. Cô lập Lỗi (Isolation):**
*   Nếu 1 việc trong TPE bị lỗi (Exception), nó không làm crash cả chương trình. TPE bắt exception đó và trả về trong đối tượng `Future`. Ta dễ dàng log lỗi và tiếp tục.
