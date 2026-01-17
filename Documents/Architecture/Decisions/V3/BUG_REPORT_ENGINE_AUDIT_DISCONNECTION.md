# Báo Cáo Lỗi Nghiêm Trọng: Mất Kết Nối Audit System trong Theus Engine V3

**Ngày báo cáo**: 2026-01-17
**Người báo cáo**: Antigravity (AI Assistant)
**Phiên bản ảnh hưởng**: Theus Framework V3 (Current Source)
**Mức độ**: CRITICAL (Nghiêm trọng)

## Tóm Tắt
Cơ chế **Audit (Quality Guard)** và chế độ **Strict Mode** bị vô hiệu hóa hoàn toàn trong Runtime do lỗi cài đặt trong lớp Python Wrapper (`theus/engine.py`). Mặc dù người dùng có thể cấu hình recipe và bật strict mode, nhưng Core Engine (Rust) không nhận được các tham số này, dẫn đến việc hệ thống hoạt động ở chế độ "Permissive" (cho phép tất cả), bỏ qua mọi vi phạm bảo mật và nghiệp vụ.

## Chi Tiết Lỗi

### Vị Trí
File: `theus/engine.py`

### 1. Strict Mode bị bỏ qua
Trong hàm `__init__` của `TheusEngine`, tham số `strict_mode` được nhận vào nhưng không được truyền xuống lớp Core.

**Code hiện tại:**
```python
class TheusEngine:
    def __init__(self, context=None, strict_mode=True, audit_recipe=None):
        # LỖI: Gọi constructor không tham số, bỏ qua strict_mode
        self._core = TheusEngineRust() 
```

**Hệ quả:** Rust Core khởi tạo với giá trị mặc định (thường là `strict_mode=False`), khiến các chốt kiểm tra an toàn (Safety Guards) bị tắt.

### 2. Audit System không được kết nối (Disconnection)
Engine khởi tạo đối tượng `AuditSystem` từ recipe, nhưng không bao giờ gán nó vào Core Engine để thực thi.

**Code hiện tại:**
```python
        if audit_recipe:
             # ... (Load logic) ...
             try:
                 from theus_core import AuditSystem
                 # LỖI: Biến self._audit được tạo ra nhưng trở thành "Dead Code"
                 self._audit = AuditSystem(rust_recipe)
             except ImportError:
                 pass
        
        # KHÔNG CÓ lệnh nào kết nối self._audit với self._core
```

**Hệ quả:**
- Các luật Audit (Input/Output rules) được load thành công vào bộ nhớ Python.
- Nhưng Rust Engine khi chạy `execute_process_async` không hề biết đến sự tồn tại của các luật này.
- Kết quả: Mọi vi phạm (VD: Số tiền âm, Ship hàng chưa thanh toán) đều được thông qua.

## Bằng Chứng (Reproduction)
Kịch bản kiểm thử `test_audit.py` cho thấy:
1.  Cấu hình `inputs: level: "BLOCK"`.
2.  Chạy Process với dữ liệu vi phạm.
3.  Kết quả: Process vẫn chạy thành công (Audit không chặn).

## Đề Xuất Khắc Phục (Hotfix Plan)

Cần sửa đổi `theus/engine.py` để kết nối lại các thành phần này.

**Mã giả đề xuất:**
```python
class TheusEngine:
    def __init__(self, context=None, strict_mode=True, audit_recipe=None):
        # 1. Truyền strict_mode xuống Core
        try:
            self._core = TheusEngineRust(strict_mode=strict_mode)
        except TypeError:
             # Fallback nếu Rust binding cũ chưa update signature
            self._core = TheusEngineRust()
            if hasattr(self._core, 'set_strict_mode'):
                self._core.set_strict_mode(strict_mode)

        # ...

        if audit_recipe:
             # ...
             self._audit = AuditSystem(rust_recipe)
             
             # 2. Kết nối Audit System vào Core
             if hasattr(self._core, 'set_audit_system'):
                 self._core.set_audit_system(self._audit)
             else:
                 # Warning: Core phiên bản này không hỗ trợ Audit Injection?
                 pass
```
