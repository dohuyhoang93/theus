# Chapter 14: Testing Strategy (Unit & Integration)

With Theus v2, you test **Code (Logic)** and **Policy (Rules)** separately.

## 1. Unit Test Logic (Process Isolation)
Since processes are just functions, test them directly. mocking the Context.

```python
class TestLogic(unittest.TestCase):
    def test_add_product_logic(self):
        # 1. Setup Mock Context
        # You can use Real Context classes too, just don't attach Engine if not needed
        ctx = WarehouseContext()
        
        # 2. Call function directly (bypass Engine/Guard for pure logic test)
        result = add_product(ctx, product_name="TestTV", price=10)
        
        # 3. Assert State
        self.assertEqual(len(ctx.domain_ctx.items), 1)
        self.assertEqual(result, "Added")
```

## 2. Integration Test Policy (Engine + Audit)
Test if Audit Rules block correctly (The "Safety Net").

```python
class TestPolicy(unittest.TestCase):
    def setUp(self):
        # Load Real Recipe
        recipe = ConfigFactory.load_recipe("audit.yaml")
        ctx = WarehouseContext()
        self.engine = TheusEngine(ctx, audit_recipe=recipe, strict_mode=True)
        self.engine.register_process("add", add_product)
        
    def test_price_blocking_policy(self):
        # Rule: Price >= 0 (Level B)
        with self.assertRaises(AuditBlockError):
            self.engine.run_process("add", product_name="BadTV", price=-5)
            
    def test_safety_interlock_policy(self):
        # Rule: Total Value < 1 billion (Level S)
        # Setup context near overflow (using edit() backdoor)
        with self.engine.edit() as safe_ctx:
             safe_ctx.domain_ctx.total_value = 999_999_999
        
        with self.assertRaises(AuditInterlockError):
             self.engine.run_process("add", product_name="OverflowTV", price=100)
```

## 3. Test FSM Workflow
Test state transition flow using `WorkflowManager` in a headless mode (no threads), just `manager.process_signal(sig)` sequentially in tests.

---
**Exercise:**
Write coverage tests for `add_product`. Ensure every line in `audit.yaml` is triggered.
