
import pytest
from dataclasses import dataclass
from theus.config import RuleSpec, ProcessRecipe, AuditRecipe
from theus.audit import AuditPolicy, AuditInterlockError, AuditBlockError

@dataclass
class MockTensor:
    val: float
    data: list = None
    def __post_init__(self):
        if self.data is None: self.data = [self.val]
    def mean(self):
        return self.val

@dataclass
class MockContext:
    score: int
    tensor: MockTensor

def test_cyclic_reset():
    """Test 'Accumulate -> Alarm -> Reset' logic."""
    # Setup
    rule = RuleSpec(
        target_field="score", 
        condition="min", 
        value=10, 
        level="C", # Warning Level (so we can check counter state without crash)
        min_threshold=0, 
        max_threshold=3,
        reset_on_success=False # Not used in new logic, but good for clarity
    )
    
    recipe = AuditRecipe(definitions={
        "p_cycle": ProcessRecipe("p_cycle", output_rules=[rule])
    })
    
    policy = AuditPolicy(recipe)
    ctx = MockContext(score=5, tensor=MockTensor(0)) # 5 < 10 -> Violation
    
    # 1. Error 1 (Count=1)
    policy.evaluate("p_cycle", "output", ctx)
    assert policy.tracker.counters["p_cycle:score:min"] == 1
    
    # 2. Success (Count should REMAIN 1)
    ctx.score = 15
    policy.evaluate("p_cycle", "output", ctx)
    assert policy.tracker.counters["p_cycle:score:min"] == 1, "Success should NOT decrease counter"
    
    # 3. Error 2 (Count=2)
    ctx.score = 5
    policy.evaluate("p_cycle", "output", ctx)
    assert policy.tracker.counters["p_cycle:score:min"] == 2
    
    # 4. Error 3 (Count=3 == Max) -> TRIGGER -> RESET
    # Since level is 'C', it logs warning and resets.
    policy.evaluate("p_cycle", "output", ctx)
    
    # Counter should be 0 (Reset triggered)
    # Wait: In logic, we record_violation (+1 -> 3), determine >= max, then reset (-> 0).
    # So checking NOW should show 0.
    assert policy.tracker.counters["p_cycle:score:min"] == 0, "Counter should reset after hitting threshold"
    
    print("[OK] Cyclic Reset Passed")

def test_dual_threshold_blocking():
    """Test Level B Block behavior."""
    rule = RuleSpec(
        target_field="score", 
        condition="max", 
        value=100, 
        level="B", # Soft Block
        min_threshold=1, 
        max_threshold=2 
    )
    
    recipe = AuditRecipe(definitions={
        "p_block": ProcessRecipe("p_block", output_rules=[rule])
    })
    
    policy = AuditPolicy(recipe)
    ctx = MockContext(score=150, tensor=MockTensor(0)) # Violation
    
    # 1. First Violation (Count=1 >= min_threshold 1) -> Warning
    # Should NOT raise exception yet
    policy.evaluate("p_block", "output", ctx)
    print("[OK] Warning Threshold Passed")
    
    # 2. Second Violation (Count=2 >= max_threshold 2) -> Block
    # Should RAISE AuditBlockError
    with pytest.raises(AuditBlockError):
        policy.evaluate("p_block", "output", ctx)
    print("[OK] Blocking Threshold Passed")

def test_computed_path():
    """Test checking tensor.mean()"""
    rule = RuleSpec(target_field="tensor.mean()", condition="max", value=0.5, level="A")
    recipe = AuditRecipe(definitions={"p_tensor": ProcessRecipe("p_tensor", output_rules=[rule])})
    
    policy = AuditPolicy(recipe)
    ctx = MockContext(score=0, tensor=MockTensor(0.8)) # 0.8 > 0.5 -> Violation
    
    with pytest.raises(AuditInterlockError):
        policy.evaluate("p_tensor", "output", ctx)
    print("[OK] Computed Path Passed")

@dataclass
class DumbObject:
    """A 3rd party object coming from a library (CANNOT MODIFY)."""
    raw_data: list

class SmartWrapper:
    """Wrapper that adds 'brain' to DumbObject."""
    def __init__(self, obj: DumbObject):
        self._obj = obj
    
    def count_zeros(self) -> int:
        return self._obj.raw_data.count(0)

def test_wrapper_pattern():
    """Test auditing a 'dumb' object using a Smart Wrapper."""
    # Logic: We want to ensure 'raw_data' has no more than 2 zeros.
    rule = RuleSpec(
        target_field="wrapper.count_zeros()", # Audit the Wrapper!
        condition="max", 
        value=2,
        level="C",
        max_threshold=5 # Ensure we don't reset immediately
    )
    
    recipe = AuditRecipe(definitions={
        "p_wrap": ProcessRecipe("p_wrap", output_rules=[rule])
    })
    
    policy = AuditPolicy(recipe)
    
    # Context has the Wrapper, which holds the Dumb Object
    dumb = DumbObject(raw_data=[0, 1, 0, 0, 5]) # Has 3 zeros -> Violation
    wrapper = SmartWrapper(dumb)
    
    @dataclass
    class LocalCtx:
        wrapper: SmartWrapper
        
    ctx = LocalCtx(wrapper=wrapper)
    
    # Should trigger violation (3 > 2)
    policy.evaluate("p_wrap", "output", ctx)
    assert policy.tracker.counters["p_wrap:wrapper.count_zeros():max"] == 1
    
    print("[OK] Wrapper Pattern Passed")

def test_audit_rollback_safety():
    """
    Verify that Audit Failure triggers Rollback (Structure Safe).
    Also demonstrates that Complex Objects are NOT Rollback Safe (In-place mutation).
    """
    from theus.engine import TheusEngine
    from theus.context import BaseSystemContext, BaseGlobalContext, BaseDomainContext
    from theus.guards import ContractViolationError
    from theus.audit import AuditBlockError # Fixed import

    # 1. Setup Context
    @dataclass
    class MyDomain(BaseDomainContext):
        my_list: list = None
        my_tensor: MockTensor = None # Complex Object

    ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=MyDomain(my_list=[], my_tensor=MockTensor(0)))
    
    # 2. Setup Audit Rule (Max list length = 0 -> Block if added)
    # 2. Setup Audit Rule (Max list length = 0 -> Block if added)
    rule = RuleSpec(
        target_field="domain_ctx.my_list", # FIX: Use Python-resolvable path for Audit
        condition="max_len", 
        value=0, 
        level="B", 
        max_threshold=1
    )
    
    recipe = AuditRecipe(definitions={
        "p_unsafe": ProcessRecipe(
            "p_unsafe", 
            # We must audit OUTPUT so it runs AFTER execution but BEFORE commit (New Flow)
            output_rules=[rule] 
        )
    })
    
    engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
    
    # 3. Define Process that mutates List AND Tensor
    def p_unsafe(ctx):
        # A. Structure Mutation (Safe)
        ctx.domain_ctx.my_list.append(1) # Access via domain_ctx (Python Object)
        
        
        # B. Complex Mutation (Unsafe In-place)
        # Using shared mutable data to prove shallow copy risk
        ctx.domain_ctx.my_tensor.data[0] = 999 

    p_unsafe._pop_contract = type("Contract", (), {
        "inputs": ["domain_ctx.my_list", "domain_ctx.my_tensor"], # Canonical Paths
        "outputs": ["domain_ctx.my_list", "domain_ctx.my_tensor"], 
        "errors": []
    })
    
    engine.register_process("p_unsafe", p_unsafe)
    
    # 4. Run -> Validates Violation
    try:
        engine.run_process("p_unsafe")
    except AuditBlockError:
        print("[OK] Correctly Caught Block Error")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")

    # 5. Verify Rollback
    # A. List should be empty (Rollback successful)
    assert len(ctx.domain_ctx.my_list) == 0, "List Structure Rollback FAILED! (New Pipeline Issue?)"
    print("[OK] List Structure Rollback OK")
    print("[OK] List Structure Rollback OK")
    
    # B. Tensor should be 0 (Rollback SUCCESS due to Deep Tracking)
    # Theus v2 ContextGuard now wraps nested lists (via .data access), ensuring tracking.
    assert ctx.domain_ctx.my_tensor.data[0] == 0, "Complex Object Rollback FAILED! (Deep Tracking should have handled this)"
    print("[OK] Complex Object Rollback Succeeded (Deep Tracking Active)")

if __name__ == "__main__":
    test_cyclic_reset()
    test_dual_threshold_blocking()
    test_computed_path()
    test_wrapper_pattern()
    test_audit_rollback_safety()
