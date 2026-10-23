**Phán quyết: sự cố có thật và được đặt đúng vào dòng thời gian — nhưng phần nguyên nhân và phần benchmark không khớp với mã nguồn.** `State` đã dùng `im::HashMap` từ trước, nên "Option A" như văn bản đề xuất là một no-op ở tầng đó; và benchmark không tái hiện được con số 7,5s mà chính văn bản lấy làm tiêu đề.

## 1. Dữ kiện kiểm chứng

**Kiểu dữ liệu thực tế** (`src/structures.rs:5` và `:199`):

```rust
use im::HashMap;                      // ← toàn bộ HashMap trong tệp là im::HashMap

pub struct State {
    pub data: HashMap<String, Arc<PyObject>>,          // im::HashMap — clone O(1)
    pub heavy: HashMap<String, Arc<PyObject>>,         // im::HashMap
    pub key_last_modified: HashMap<String, u64>,       // im::HashMap
    pub last_signals: HashMap<String, String>,         // im::HashMap
}
```

**Chạy `tests/perf/burst_write_benchmark.py`** (máy này, tiến trình riêng):

| Scenario | N=100 | N=500 | N=1000 | Hình dạng |
|---|---|---|---|---|
| 3. Nested `domain.counter` | — | 7,17 µs/op | 6,97 µs/op | phẳng |
| 4. Context + proxy | 20,13 µs/op | 20,44 µs/op | 16,49 µs/op | phẳng |
| 5. Prepopulated 5.000 khóa | 465 µs/op | 514 µs/op | 436 µs/op | **phẳng nhưng cao 25×** |

## 2. Bốn khiếm khuyết

### 2.1. Nguyên nhân được nêu đã được giải quyết từ trước

Văn bản nói `State::update()` sao chép toàn bộ `documents` N phần tử, và đề xuất thay `HashMap` bằng `im::HashMap`. Nhưng `data`, `heavy`, `key_last_modified`, `last_signals` **đều đã là** `im::HashMap`, nên `self.data.clone()` là O(1) — đúng như INC-030 mong muốn.

Chi phí quan sát được ở Scenario 5 có dấu hiệu khác hẳn: **~450–500 µs/op không đổi** khi N tăng, tức chi phí tỉ lệ với **kích thước state ban đầu (K=5000)**, không tỉ lệ với số lần ghi. Đó là chữ ký của một phép sao chép **một lần cho mỗi transaction**, không phải của clone trong `update()`. Ứng viên: `src/engine.rs:881` — `copy_mod.call_method1("deepcopy", (&val,))` trong cơ chế shadow, cùng các chú thích về "Transaction isolation failure: cannot deepcopy". Đây là **giả thuyết**, cần profile để xác nhận, nhưng nó khớp với dữ liệu hơn hẳn giả thuyết trong văn bản.

Trớ trêu: nếu ai đó triển khai đúng "Option A" như viết, họ sẽ không thấy cải thiện nào — vì nó đã được làm rồi.

### 2.2. Benchmark không tái hiện con số tiêu đề

Con số 7,5s (và 27,85s ở N=2000 trong phép đo của tôi) đến từ việc ghi vào **một sub-dict tăng dần** — `domain.documents[doc_id]` — nơi `deep_merge_cow` sao chép toàn bộ dict N phần tử mỗi lần commit.

Benchmark hiện có năm scenario, **không scenario nào làm việc đó**:
- Scenario 3 ghi `domain.counter` — một khóa duy nhất, dict không lớn lên.
- Scenario 2 ghi khóa ở tầng ngoài, không đi qua `deep_merge_cow`.

Nên `burst_write_benchmark.py` đo một đường khác với đường đã sinh ra 7,5s. Đây là lỗ hổng nghiêm trọng nhất: văn bản dẫn benchmark làm bằng chứng cho một hiện tượng mà benchmark không chạm tới.

### 2.3. Benchmark không phải cổng kiểm

Acceptance criterion #3 và Prevention #1 đều nói benchmark phải **fail CI** khi vượt ngưỡng. Mã hiện tại chỉ `print`, không so ngưỡng, không `sys.exit(1)`, không được gọi trong `Local_CI.py`. Như viết, nó là báo cáo, không phải cổng.

Ngoài ra: tham số mặc định mutable `n_list=[100, 500, 1000]` (không bị sửa nên chưa gây lỗi, nhưng là mẫu xấu), và không đo bộ nhớ — trong khi CoW là câu chuyện về cả thời gian lẫn bộ nhớ.

### 2.4. Số liệu nội bộ mâu thuẫn và tên trường không tồn tại

- Summary ghi N=1000 ≈ **7,5s**; §8.4 Scenario 2 ghi N=1000 = **0,0475s**. Hai con số chênh 158 lần, vì chúng đo hai workload khác nhau dưới cùng nhãn "burst". Cần tách nhãn: *growing nested sub-dict* và *distinct top-level keys*.
- `State` **không có** trường `documents`; trường là `data`. Pseudocode và đoạn Option A đều viết `documents`, nên người triển khai theo văn bản sẽ đi tìm một trường không tồn tại.
- `fixed_in: ~` là placeholder; nên ghi `— (open)` như INC-029.

## 3. Phần văn bản làm đúng

- Đặt đúng dòng thời gian: **không phải hồi quy của v3.0.27**; mốc 45,6s trước bản vá cùng profile. Điều này khớp với phép đo của tôi (42,35s sau bản vá).
- Ghi nhận phép thử phủ định `_sync_registry_from_core` và kết luận đúng: < 2%, không phải nguyên nhân.
- Tách "snapshot isolation" (bất biến ngữ nghĩa) khỏi "full copy" (lựa chọn triển khai) — đây là cách đặt vấn đề đúng.
- Bài học #3 về đo lường trong môi trường nhiễu là chính xác và nên giữ.

## 4. Việc cần làm để INC-030 đứng được

1. **Thêm Scenario 6**: ghi `domain.documents[doc_id]` với N tăng dần — đúng workload sinh ra 7,5s. Không có nó, benchmark không bảo vệ được gì.
2. **Profile để định vị chi phí O(K) mỗi transaction**: so sánh thời gian `with e.transaction(): pass` trên engine có 0 / 1.000 / 5.000 khóa. Nếu thời gian tăng theo K, nguyên nhân nằm ở snapshot/deepcopy chứ không ở `update()`.
3. **Sửa văn bản**: `documents` → `data`; ghi rõ `im::HashMap` đã có; đổi Option A thành "áp delta vào zone payload" hoặc "bỏ deepcopy mỗi transaction".
4. **Biến benchmark thành cổng**: ngưỡng, `sys.exit(1)`, gọi từ `Local_CI.py full`.
5. **Tách hai nhãn workload** trong bảng số liệu, và ghi rõ mốc nào đo cái gì.

## 5. Kết luận

Sự cố **có thật**, mức `medium` hợp lý, và việc mở nó là đúng. Nhưng nếu triển khai theo đúng văn bản hiện tại — chuyển `HashMap` sang `im::HashMap` — sẽ không có thay đổi đo được, vì tầng đó đã là persistent từ trước. Cần chuyển trọng tâm từ "clone trong `update()`" sang "sao chép theo mỗi transaction và `deep_merge_cow` trên sub-dict tăng dần", rồi để benchmark chứng minh.