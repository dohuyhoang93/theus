# Chapter 14: Testing - Strategy v2

With Theus v2, you don't just test code logic, you test **Policy** and **Config** too.

## 1. Unit Test Logic (Process)
Test `@process` function independently, without Engine.
```python
class TestLogic(unittest.TestCase):
    def test_add_product(self):
        # 1. Setup Mock Context
        ctx = MockContext(domain=MockDomain(items=[]))
        
        # 2. Call function directly (bypass Engine)
        # Note: Need to mock ContextGuard if function uses complex Guard logic
        add_product(ctx, name="A", price=10)
        
        # 3. Assert
        self.assertEqual(len(ctx.domain.items), 1)
```

## 2. Integration Test Policy (Engine + Audit)
Test if Audit Rules block correctly.
```python
class TestPolicy(unittest.TestCase):
    def setUp(self):
        # Load Real Recipe
        recipe = ConfigFactory.load_recipe("audit.yaml")
        self.engine = TheusEngine(sys_ctx, audit_recipe=recipe)
        self.engine.register_process("add", add_product)
        
    def test_price_block(self):
        # Rule: Price >= 0 (Level B)
        with self.assertRaises(AuditBlockError):
            self.engine.run_process("add", name="B", price=-5)
            
    def test_safety_interlock(self):
        # Rule: Total Value < 1 billion (Level S)
        # Setup context near overflow
        self.engine.ctx.domain.total_value = 999_999_999
        
        with self.assertRaises(AuditInterlockError):
             self.engine.run_process("add", name="C", price=100)
```

## 3. Test FSM Workflow
Test state transition flow.
- Use `WorkflowManager` and simulate emitting Signals.
- Assert that `current_state` moves correctly from `IDLE` -> `PROCESSING`.

---
**Exercise:**
Write coverage tests for both Logic (Process) and Policy (Audit) of the warehouse app. Ensure every line in `audit.yaml` is triggered at least once.
