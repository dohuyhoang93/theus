**Phán quyết: ba điểm tôi nêu đã được sửa đúng, và bản triển khai xanh trên cả ba tầng.** Nhưng lần chạy này phát hiện một hệ quả định lượng mà các vòng trước chỉ dự đoán: **toàn bộ suite chậm đi 2,4 lần** — 45,61s → 109,87s — và một test đơn lẻ chiếm 23,4s trong đó.

---

## 1. Ba điểm đã sửa

| Điểm | Kết quả |
|---|---|
| Lệnh lùi phủ đủ tệp | ✅ Nay có 8 tệp + phương án `git stash`. Vẫn còn một lỗ hổng nhỏ — xem §4 |
| Ghi nhận ba lệch tài liệu | ✅ `heavy_dict` (dòng 77), `_sync_degraded` (dòng 351), bình luận 644 → 670 |
| `downcast` trong `structures.rs` | ✅ **Đã hoàn lại `?`**, kèm chú thích nêu rõ lý do: bỏ qua im lặng sẽ làm signal biến mất không dấu vết, tái sinh đúng lớp lỗi INC-023 |

Điểm thứ ba là quan trọng nhất, và cách sửa đúng: không chỉ khôi phục hành vi cũ mà còn ghi lý do tại chỗ, để lần sau không ai "tối ưu" nó thành `if let Ok` lần nữa.

## 2. Kết quả chạy test — trên bản biên dịch mới

Nguồn được sửa lúc 16:51; tôi rebuild lúc 16:57 (`Local_CI.py build`, 6,16s, exit 0), nên test chạy trên mã mới chứ không phải artefact cũ.

| Lần chạy | Kết quả |
|---|---|
| `verify_occ_vulnerability_matrix.py` | **17 passed**, 2,34s |
| `verify_transaction_occ_gap.py` | **15 passed**, 1,24s |
| Toàn bộ `tests/` | **490 passed, 3 skipped**, 109,87s |
| `test_case3_bien_burst_no_document_loss` (riêng) | **passed**, 23,39s |

## 3. Phát hiện: suy giảm hiệu năng đo được

Cùng 490 test, cùng máy:

| Bản | Thời gian toàn suite |
|---|---|
| Trước thay đổi | **45,61s** |
| Sau thay đổi | **109,87s** |

Chênh **+64,3s (+141%)**. Một test — 1000 lần ghi tuần tự vào `domain.documents` — chiếm 23,4s khi chạy riêng.

**Giả thuyết có căn cứ:** `@property state` gọi `_sync_registry_from_core()` mỗi khi version đổi. Mỗi commit đều đổi version, nên với n lần ghi tuần tự, chi phí là **O(n²)** theo kích thước state: mỗi lần đồng bộ lại validate toàn bộ `domain` qua Pydantic. Đây đúng rủi ro tôi nêu ở vòng 3 và vòng 4, và kế hoạch đã chấp nhận với lý lẽ "chỉ chạy khi version đổi" — đúng, nhưng **mỗi commit đều làm version đổi**, nên điều kiện đó không bảo vệ được gì trong tác vụ ghi tuần tự.

**Cách xác nhận trong một lệnh:** chạy lại test burst với `_sync_registry_from_core` bị vô hiệu tạm thời. Nếu thời gian về mức cũ, giả thuyết được xác lập — chi phí khoảng 2 phút.

**Hướng sửa, nếu xác nhận:** đồng bộ theo trường đã đổi thay vì toàn bộ state; hoặc chuyển sync về đường ghi (một lần sau commit) thay vì lazy trên đường đọc.

**Một điểm phụ:** trong một lần chạy đầy tải, `test_stress_concurrent_publish_subscribe` báo FAILED; chạy riêng thì pass trong 1,56s. Đó là flaky phụ thuộc tải, không phải lỗi xác định — nhưng nên ghi nhận vì nó nằm trong vùng signal.

## 4. Hai ghi chú nhỏ còn lại

- **Lệnh lùi vẫn chưa phủ phần xoá.** `git restore` với 8 tệp không khôi phục các `RELEASE_NOTES_*.md` đã xoá và `RFC_004` đã chuyển thư mục. Cây hiện có 29 đường dẫn thay đổi. `git stash -u` phủ hết; nên đặt nó làm phương án chính, `git restore` làm phương án phụ.
- **Số dòng bình luận: kế hoạch ghi 670, thực tế 673.** Lệch ba dòng, không ảnh hưởng gì, nhưng vì đây là con số đã hai lần trôi, nên sửa cho khớp.

---

**Kết luận.** Phần đúng đắn đã đóng: 17/17, 15/15, 490 passed, và lỗ hổng fail-open trong đường signal đã được hoàn lại thành fail-fast. Phần còn mở là **hiệu năng**, và nó không chặn bản vá — nhưng nó chạm đúng hướng bạn đang cân nhắc (framework cho tác vụ LLM, nơi mỗi bước là một lần ghi tuần tự vào state lớn dần). Nên tách thành một sự cố riêng thay vì để nó nằm lẫn trong INC-029.

Tôi đã ghi phần này vào cuối `INC-029` — bảng kiểm chứng và ghi chú hiệu năng 45,61s → 109,87s. Tệp hiện 15.031 byte.

**Đính chính một điểm trong báo cáo trước.** Lần chạy mà tôi tưởng đã bị kill thực ra **đã hoàn tất** — và nó kết thúc với một test thất bại khác. Điều này đổi kết luận: bộ test đầy đủ **không xác định**, không phải xanh tuyệt đối.

## Ba lần chạy toàn bộ, cùng một bản biên dịch

| Lần | Kết quả | Thời gian |
|---|---|---|
| Lần 1 (nền, tưởng đã kill) | **1 failed**, 489 passed, 3 skipped — `tests/integration/test_zero_copy_proof.py::TestZeroCopyProof::test_proof` | 113,41s |
| Lần 2 (verbose, tôi kill giữa chừng) | quan sát thấy `test_stress_concurrent_publish_subscribe` FAILED | — |
| Lần 3 (sạch) | **490 passed**, 3 skipped | 109,87s |

Hai lần, hai test khác nhau thất bại; lần thứ ba không có lỗi. Đó là mẫu của **flaky do tải**, không phải lỗi xác định.

## Kiểm chứng từng test riêng lẻ

| Test | Chạy riêng | Kết quả |
|---|---|---|
| `test_zero_copy_proof::test_proof` | 3 lần | **3/3 pass** (5,09s · 2,21s · 2,40s) |
| `test_stress_concurrent_publish_subscribe` | 1 lần | pass (1,56s) |
| `test_case3_bien_burst_no_document_loss` | 1 lần | pass (23,39s) |

Kết luận có căn cứ: cả hai test đều đúng khi chạy một mình, chỉ hỏng khi chạy trong toàn bộ suite. Nên không phải lỗi logic của bản vá, mà là **tương tác giữa các test hoặc phụ thuộc thời điểm** — và nó xuất hiện trên đúng bản biên dịch mới.

## Điều này thay đổi gì trong đánh giá

- **Hai suite mục tiêu vẫn ổn định:** 17/17 và 15/15, chạy lại nhiều lần không đổi.
- **Không thể nói "toàn bộ 490 test xanh"** như một khẳng định. Phát biểu đúng: *một trong ba lần chạy sạch; hai lần còn lại mỗi lần một test flaky.*
- **Suy giảm hiệu năng vẫn đứng:** 45,61s → 109,87s, tức 2,4 lần. Con số này không phụ thuộc flakiness.

## Hai việc nên làm trước khi cắt bản phát hành

1. **Chạy toàn bộ suite 5 lần liên tiếp** và đếm tỉ lệ hỏng của từng test. Nếu `zero_copy_proof` và `signalhub_stress` hỏng ≥1/5, chúng cần được xử lý như lỗi thật — nhiều khả năng là giả định về thời điểm hoặc về trạng thái chia sẻ giữa các test, không phải về OCC.
2. **Xác nhận giả thuyết O(n²)** bằng cách chạy test burst với `_sync_registry_from_core` bị vô hiệu tạm. Nếu thời gian về mức cũ, nguyên nhân được xác lập và hướng sửa đã rõ.

Tôi đã ghi cả hai điểm vào `INC-029`: bảng kiểm chứng và ghi chú hiệu năng. Phần còn lại — flakiness — nên là một mục riêng, vì nó không thuộc INC-029.

