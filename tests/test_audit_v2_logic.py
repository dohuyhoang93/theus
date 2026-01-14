import pytest
import unittest
from dataclasses import dataclass
from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext
from theus.config import RuleSpec, ProcessRecipe, AuditRecipe
from theus.audit import AuditInterlockError, AuditBlockError

# --- SHARED DATA STRUCTURES ---

@dataclass
class MockTensor:
    val: float
    data: list = None
    def __post_init__(self):
        if self.data is None: self.data = [self.val]
    def __copy__(self):
        return MockTensor(self.val, self.data[:])
    def mean(self):
        return self.val

@dataclass
class MockDomain(BaseDomainContext):
    score: int = 0
    tensor: MockTensor = None
    
@process(inputs=['domain_ctx.score', 'domain_ctx.tensor'], outputs=['domain_ctx.score'])
def p_cycle(ctx): pass

@process(inputs=['domain_ctx.score'], outputs=['domain_ctx.score'])
def p_block(ctx): pass

@process(inputs=['domain_ctx.tensor'], outputs=['domain_ctx.tensor'])
def p_tensor(ctx): pass

@dataclass
class DumbObject:
    raw_data: list

class SmartWrapper:
    def __init__(self, obj: DumbObject):
        self._obj = obj
    def count_zeros(self) -> int:
        return self._obj.raw_data.count(0)

@dataclass
class WrapperDomain(BaseDomainContext):
    wrapper: SmartWrapper = None

@process(inputs=['domain_ctx.wrapper'], outputs=[])
def p_wrap(ctx): pass


class TestAuditV2Logic(unittest.TestCase):
    
    def test_cyclic_reset_blackbox(self):
        """Test 'Accumulate -> Alarm -> Reset' logic via strictly observable behavior."""
        print("\n--- Test Cyclic Reset (Blackbox) ---")
        # Rule: Min threshold 0, Max threshold 3 -> Block on 3rd violation
        rule = RuleSpec(
            target_field="domain_ctx.score", 
            condition="min", 
            value=10, 
            level="B", # BLOCKING for observability
            min_threshold=0, 
            max_threshold=3,
            reset_on_success=False
        )
        recipe = AuditRecipe(definitions={
            "p_cycle": ProcessRecipe("p_cycle", output_rules=[rule])
        })
        
        dom = MockDomain(score=5, tensor=MockTensor(0)) # Violation (5 < 10)
        ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=dom)
        
        engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
        engine.register_process("p_cycle", p_cycle)
        
        # 1. Error 1 (Count=1) -> Warning
        engine.run_process("p_cycle")
        
        # 2. Error 2 (Count=2) -> Warning
        engine.run_process("p_cycle")
        
        # 3. Error 3 (Count=3 == Max) -> BLOCK
        with self.assertRaises(AuditBlockError):
            engine.run_process("p_cycle")
        print("   -> Caught explicit block on 3rd attempt.")

        # 4. Error 4 (Should be Count=1 due to Reset) -> Warning
        engine.run_process("p_cycle")
        print("   -> 4th attempt succeeded (Reset confirmed).")

    def test_dual_threshold_blocking(self):
        """Test Level B Block behavior."""
        # Rule: Warn at 1, Block at 2
        rule = RuleSpec(
            target_field="domain_ctx.score", condition="max", value=100, 
            level="B", min_threshold=1, max_threshold=2 
        )
        recipe = AuditRecipe(definitions={"p_block": ProcessRecipe("p_block", output_rules=[rule])})
        
        dom = MockDomain(score=150, tensor=MockTensor(0)) # Violation
        ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=dom)
        
        engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
        engine.register_process("p_block", p_block)
        
        # 1. First Violation (Count=1) -> Warning (No Block)
        engine.run_process("p_block")
        
        # 2. Second Violation (Count=2) -> Block
        with self.assertRaises(AuditBlockError):
            engine.run_process("p_block")

    def test_computed_path(self):
        """Test checking tensor.mean()"""
        rule = RuleSpec(target_field="domain_ctx.tensor.mean()", condition="max", value=0.5, level="A")
        recipe = AuditRecipe(definitions={"p_tensor": ProcessRecipe("p_tensor", output_rules=[rule])})
        
        dom = MockDomain(score=0, tensor=MockTensor(0.8)) # 0.8 > 0.5 -> Violation
        ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=dom)
        
        engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
        engine.register_process("p_tensor", p_tensor)
        
        # Interlock Error (Level A)
        with self.assertRaises(AuditInterlockError):
            engine.run_process("p_tensor")

    def test_wrapper_pattern(self):
        """Test auditing a 'dumb' object using a Smart Wrapper."""
        rule = RuleSpec(
            target_field="domain_ctx.wrapper.count_zeros()", 
            condition="max", value=2, level="B", max_threshold=1
        )
        recipe = AuditRecipe(definitions={"p_wrap": ProcessRecipe("p_wrap", output_rules=[rule])})
        
        dumb = DumbObject(raw_data=[0, 1, 0, 0, 5]) # 3 zeros -> Violation
        dom = WrapperDomain(wrapper=SmartWrapper(dumb))
        ctx = BaseSystemContext(global_ctx=BaseGlobalContext(), domain_ctx=dom)
        
        engine = TheusEngine(ctx, strict_mode=True, audit_recipe=recipe)
        engine.register_process("p_wrap", p_wrap)
        
        # Violation -> Block
        with self.assertRaises(AuditBlockError):
            engine.run_process("p_wrap")

if __name__ == "__main__":
    unittest.main()
