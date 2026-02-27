import pytest
import os
import yaml
from pathlib import Path
from theus.context import BaseSystemContext, BaseGlobalContext, BaseDomainContext, NamespaceRegistry
from theus.linter import run_lint
from theus.schema_gen import generate_schema_from_file, generate_code_from_schema

def test_basesystemcontext_dynamic_access():
    NamespaceRegistry().clear()
    NamespaceRegistry().register("trading", default_data={"balance": 1000})
    
    # Mock a system context with state
    class SimpleState:
        def __init__(self, data):
            self.data = data
            
    ctx = BaseSystemContext(global_ctx=None, domain=None)
    ctx._state = SimpleState(data={"trading": {"balance": 1000}})
    
    # Verify dynamic access
    assert ctx.trading == {"balance": 1000}
    
    with pytest.raises(AttributeError):
        _ = ctx.non_existent

def test_schema_gen_roundtrip_namespaces(tmp_path):
    NamespaceRegistry().clear()
    
    # 1. Create a Schema with custom namespaces
    schema_yaml = {
        "context": {
            "global": {"version": {"type": "string", "default": "1.0"}},
            "domain": {"user": {"type": "string"}},
            "inventory": {"stock": {"type": "integer", "default": 100}}
        }
    }
    
    schema_file = tmp_path / "schema.yaml"
    with open(schema_file, "w") as f:
        yaml.dump(schema_yaml, f)
        
    # 2. Generate Code
    code = generate_code_from_schema(str(schema_file))
    
    # 3. Verify Code Structure
    assert "class AppGlobal(BaseGlobalContext):" in code
    assert "class AppDomain(BaseDomainContext):" in code
    assert "class InventoryContext(BaseDomainContext):" in code
    assert "class SystemContext(BaseSystemContext):" in code
    assert "inventory: InventoryContext" in code
    
    # 4. Save code and try to parse back to schema (Integration test)
    context_py = tmp_path / "context_generated.py"
    with open(context_py, "w") as f:
        f.write(code)
        
    # We must register the namespace for the generator to pick it up as a context
    NamespaceRegistry().register("inventory")
    
    new_schema = generate_schema_from_file(str(context_py))
    assert "inventory" in new_schema["context"]
    assert new_schema["context"]["inventory"]["stock"]["type"] == "integer"

def test_linter_namespace_awareness(tmp_path):
    NamespaceRegistry().clear()
    NamespaceRegistry().register("trading")
    
    # 1. Create a process file with undeclared namespace access
    process_code = """from theus.contracts import process

@process(inputs=["domain.user"])
async def p_bad_access(ctx):
    # 'trading' is registered but not in inputs
    return ctx.trading.balance
"""
    process_file = tmp_path / "process_bad.py"
    with open(process_file, "w") as f:
        f.write(process_code)
        
    # 2. Run Linter
    # We expect a POP-C01 violation for 'trading.balance'
    from theus.linter import POPLinter
    import ast
    
    with open(process_file, "r") as f:
        tree = ast.parse(f.read())
        
    linter = POPLinter(str(process_file))
    linter.visit(tree)
    
    # Print violations for debugging if test fails
    print(f"DEBUG: Found {len(linter.violations)} violations: {[v.check_id for v in linter.violations]}")
    for v in linter.violations:
        print(f"  - {v.message}")

    violations = [v.check_id for v in linter.violations]
    assert "POP-C01" in violations
    assert any("trading.balance" in v.message for v in linter.violations)

def test_linter_namespace_physics(tmp_path):
    NamespaceRegistry().clear()
    NamespaceRegistry().register("trading")
    
    # 1. Create a process file with a paradoxical mutation (RFC-001)
    # Mutation on meta_ is forbidden.
    process_code = """from theus.contracts import process

@process(inputs=["trading.meta_config"])
async def p_bad_physics(ctx):
    # RFC-001 says meta_ is Read-Only.
    # This should be flagged as POP-E07 or POP-E05.
    ctx.trading.meta_config.update({"rate": 0.5}) 
    return {}
"""
    process_file = tmp_path / "process_physics.py"
    with open(process_file, "w") as f:
        f.write(process_code)
        
    from theus.linter import POPLinter
    import ast
    with open(process_file, "r") as f:
        tree = ast.parse(f.read())
        
    linter = POPLinter(str(process_file))
    linter.visit(tree)
    
    violations = [v.check_id for v in linter.violations]
    # Expect POP-E07 (Behavioral Paradox) for mutation on restricted zone
    assert "POP-E07" in violations

def test_declarative_namespace_registration():
    NamespaceRegistry().clear()
    from theus.context import Namespace, NamespacePolicy
    
    # Define a custom context class
    class StrategyContext(BaseDomainContext):
        pass
        
    # [RFC-001 Handbook Pattern]
    class AlgoTradingContext(BaseSystemContext):
        strategy = Namespace(StrategyContext, policy=NamespacePolicy(allow_update=False))
        
    # Verify registration happened via __set_name__
    registry = NamespaceRegistry()
    assert "strategy" in registry._namespaces
    assert registry.get_policy("strategy").allow_update is False

if __name__ == "__main__":
    pytest.main([__file__])
