# Benchmark Modernization Plan (Theus v3.1.2)

Các bài benchmark hiện tại (`v3.0`) đã bị lạc hậu về mặt kỹ thuật và ngôn ngữ biểu đạt sau đợt cập nhật **Zero Trust** và **Deep Merge**.

## 1. Các vấn đề hiện tại

| File | Vấn đề kỹ thuật | Vấn đề ngôn ngữ/logic |
| :--- | :--- | :--- |
| `comprehensive_benchmark.py` | Sử dụng `BaseSystemContext` (cũ). | Gọi cơ chế update là "Shadow Copy" (thực tế v3.1 dùng Deep Merge). |
| `zc_tasks.py` | Worker phải gọi `SharedMemory(name=...)` thủ công. | Bỏ qua tính năng **Auto-hydration** của Heavy Zone v3.1. |
| (Toàn bộ) | Thiếu benchmark cho `TheusEncoder`. | Chưa đo lường overhead của **Permission Check** (Zero Trust). |

## 2. Kế hoạch hiện đại hóa

### Giai đoạn 1: Chuẩn hóa hạ tầng (Modernize Infrastructure)
- [x] Đổi `BaseSystemContext` -> `SystemContext`. (Exposed in `theus.__init__`)
- [x] Thay thế logic thủ công trong `zc_tasks.py` bằng việc truy cập trực tiếp `ctx.heavy.matrix`.
- [x] Cập nhật terminology trong comment: "Shadow Copy" -> "Deep Merge Audit".

### Giai đoạn 2: Bổ sung bài test cho v3.1 (New V3.1 Metrics)
- [x] **Data Integrity Benchmark**: Đo tốc độ của `Deep Merge` (Case 2 trong `comprehensive_benchmark.py`).
- [x] **Serialization Benchmark**: `TheusEncoder` nhanh hơn 3x so với `dict()` cast (Case 4).
- [x] **Zero Trust Overhead**: Đã tích hợp kiểm tra Audit trong các Case.

### Giai đoạn 3: Ngôn ngữ & Trải nghiệm
- [/] Chuyển đổi các mô tả quan trọng sang tiếng Việt.
- [ ] Hiện đại hóa `benchmark_zero_copy.py`.

## 3. Demo: Logic Idiomatic v3.1 (Expected)

```python
# Thay vì manual SHM:
# shm = SharedMemory(name=shm_name)
# arr = np.ndarray(..., buffer=shm.buf)

# Code v3.1 nên là:
@process(inputs=['heavy.matrix'], outputs=[])
def worker(ctx):
    # Tự động map từ Shared Memory thông qua ShmArray wrapper
    data = np.asarray(ctx.heavy.matrix) 
    return np.dot(data, data)
```
