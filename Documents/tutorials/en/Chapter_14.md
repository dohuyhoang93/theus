# Chapter 14: Testing Strategy (Unit & Integration)

With Theus v3.0, you test **Code (Logic)** and **Policy (Rules)** separately.

## 1. Unit Test Logic (Process Isolation)
Since processes are just functions, test them directly, mocking the Context.

```python
import unittest
from my_app.context import WarehouseContext
from my_app.processes import add_product

class TestLogic(unittest.TestCase):
    def test_add_product_logic(self):
        # 1. Setup Mock Context
        # You can use Real Context classes too, just don't attach Engine if not needed
        ctx = WarehouseContext()
        
        # 2. Call function directly (Pure Logic Test)
        # Note: In V3, processes return data, they don't mutate ctx directly
        new_items, new_total, _ = add_product(ctx, product_name="TestTV", price=10)
        
        # 3. Assert Result Data
        self.assertEqual(len(new_items), 1)
        self.assertEqual(new_total, 10)
```

## 2. Integration Test Policy (Engine + Audit)
Test if Audit Rules block correctly (The "Safety Net").

```python
from theus import TheusEngine
from theus_core import AuditBlockError, AuditStopError

class TestPolicy(unittest.TestCase):
    def setUp(self):
        ctx = WarehouseContext()
        self.engine = TheusEngine(
            ctx,
            strict_mode=True,
            audit_recipe="specs/audit.yaml"
        )
        self.engine.register(add_product)
        
    def test_price_blocking_policy(self):
        # Rule: Price >= 0 (Level B)
        with self.assertRaises(AuditBlockError):
            self.engine.execute(add_product, product_name="BadTV", price=-5)
            
    def test_safety_interlock_policy(self):
        # Rule: Total Value < 1 billion (Level S)
        # Setup context near overflow (using edit() backdoor)
        with self.engine.edit() as safe_ctx:
             safe_ctx.domain_ctx.total_value = 999_999_999
        
        with self.assertRaises(AuditStopError):
             self.engine.execute(add_product, product_name="OverflowTV", price=100)
```

## 3. Test Flux DSL Workflow

Test workflow execution using `WorkflowEngine`:

```python
from theus_core import WorkflowEngine, FSMState

class TestWorkflow(unittest.TestCase):
    def test_workflow_execution(self):
        yaml_config = """
steps:
  - process: "step_a"
  - process: "step_b"
"""
        workflow = WorkflowEngine(yaml_config, max_ops=100)
        
        # Check initial state
        self.assertEqual(workflow.state, FSMState.Pending)
        
        # Mock executor
        executed = []
        def mock_executor(name):
            executed.append(name)
        
        # Execute
        ctx = {"domain": {}, "global": {}}
        workflow.execute(ctx, mock_executor)
        
        # Verify
        self.assertEqual(workflow.state, FSMState.Complete)
        self.assertEqual(executed, ["step_a", "step_b"])
```

## 4. POP Linter

Use the CLI linter to check for common violations:

```bash
py -m theus.cli check src/processes
```

This checks for:
- POP-E01: No `print()` - Use `ctx.log`
- POP-E02: No `open()` - Use Outbox
- POP-E03: No `requests` - No direct HTTP
- POP-E04: No `global` - Strict Context

---
**Exercise:**
Write coverage tests for `add_product`. Ensure every line in `audit.yaml` is triggered.
