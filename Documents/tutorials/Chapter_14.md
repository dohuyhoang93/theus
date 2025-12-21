# Chương 14: Testing - Chiến lược kiểm thử v2

Với Theus v2, bạn không chỉ test logic code, bạn test cả **Chính sách (Policy)** và **Cấu hình (Config)**.

## 1. Unit Test Logic (Process)
Test hàm `@process` độc lập, không cần Engine.
```python
class TestLogic(unittest.TestCase):
    def test_add_product(self):
        # 1. Setup Mock Context
        ctx = MockContext(domain=MockDomain(items=[]))
        
        # 2. Call function directly (bypass Engine)
        # Lưu ý: Cần mock ContextGuard nếu hàm dùng logic phức tạp của Guard
        add_product(ctx, name="A", price=10)
        
        # 3. Assert
        self.assertEqual(len(ctx.domain.items), 1)
```

## 2. Integration Test Policy (Engine + Audit)
Test xem luật Audit có chặn đúng không.
```python
class TestPolicy(unittest.TestCase):
    def setUp(self):
        # Load Real Recipe
        recipe = ConfigFactory.load_recipe("audit.yaml")
        self.engine = TheusEngine(sys_ctx, audit_recipe=recipe)
        self.engine.register_process("add", add_product)
        
    def test_price_block(self):
        # Luật: Price >= 0 (Level B)
        with self.assertRaises(AuditBlockError):
            self.engine.run_process("add", name="B", price=-5)
            
    def test_safety_interlock(self):
        # Luật: Total Value < 1 tỷ (Level S)
        # Setup ngữ cảnh sắp tràn
        self.engine.ctx.domain.total_value = 999_999_999
        
        with self.assertRaises(AuditInterlockError):
             self.engine.run_process("add", name="C", price=100)
```

## 3. Test FSM Workflow
Kiểm tra luồng chuyển trạng thái.
- Dùng `WorkflowManager` và giả lập bắn Signal.
- Assert rằng `current_state` chuyển đúng từ `IDLE` -> `PROCESSING`.

---
**Thực hành:**
Viết bộ test phủ (Coverage) cho cả Logic (Process) và Policy (Audit) của ứng dụng kho hàng. Đảm bảo mọi dòng trong file `audit.yaml` đều được test kích hoạt ít nhất 1 lần.