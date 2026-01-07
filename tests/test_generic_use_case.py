import unittest
from dataclasses import dataclass, field
from typing import List, Dict

# Import from LOCAL SDK (Relative import or sys path hack needed if not installed)

from theus import TheusEngine, process, BaseSystemContext, BaseGlobalContext, BaseDomainContext, ContractViolationError

# --- 1. Define Domain Logic (Bread Factory) ---

@dataclass
class BakeryConfig(BaseGlobalContext):
    flour_per_loaf: int = 2
    oven_capacity: int = 5

@dataclass
class BakeryState(BaseDomainContext):
    flour_stock: int = 100
    loaves_baked: int = 0
    oven_temp: int = 0

@dataclass
class BakerySystem(BaseSystemContext):
    global_ctx: BakeryConfig
    domain_ctx: BakeryState
    # Extra layer?
    user_ctx: Dict = field(default_factory=dict) # Should be ignored by engine unless wrapped

# --- 2. Define Processes ---

@process(
    inputs=['domain_ctx.flour_stock', 'global_ctx.flour_per_loaf', 'domain_ctx.loaves_baked'],
    outputs=['domain_ctx.flour_stock', 'domain_ctx.loaves_baked'],
    errors=['ValueError']
)
def bake_bread(ctx: BakerySystem, quantity: int):
    domain = ctx.domain_ctx
    config = ctx.global_ctx
    
    needed = quantity * config.flour_per_loaf
    
    if domain.flour_stock < needed:
        raise ValueError("Not enough flour!")
        
    domain.flour_stock -= needed
    domain.loaves_baked += quantity
    return f"Baked {quantity} loaves."

@process(
    inputs=['domain_ctx.flour_stock'], # Missing 'global_ctx.flour_per_loaf'
    outputs=['domain_ctx.loaves_baked']
)
def bad_baker_read(ctx: BakerySystem):
    # Tries to read global config without declaring input
    needed = ctx.global_ctx.flour_per_loaf 
    pass

@process(
    inputs=['domain_ctx.flour_stock'],
    outputs=[] # Missing 'domain_ctx.flour_stock'
)
def bad_baker_write(ctx: BakerySystem):
    # Tries to modify stock without declaring output
    ctx.domain_ctx.flour_stock -= 10
    pass

# --- 3. Test Suite ---

class TestGenericBakery(unittest.TestCase):
    def setUp(self):
        self.sys = BakerySystem(
            global_ctx=BakeryConfig(),
            domain_ctx=BakeryState()
        )
        self.engine = TheusEngine(self.sys)
        self.engine.register_process("bake", bake_bread)
        self.engine.register_process("bad_read", bad_baker_read)
        self.engine.register_process("bad_write", bad_baker_write)

    def test_successful_flow(self):
        try:
            print("\n[Bakery] Testing Valid Flow...")
            res = self.engine.run_process("bake", quantity=10)
            self.assertEqual(res, "Baked 10 loaves.")
            self.assertEqual(self.sys.domain_ctx.loaves_baked, 10)
            self.assertEqual(self.sys.domain_ctx.flour_stock, 80) # 100 - 20
            print("   -> Success.")
        except Exception as e:
            import traceback
            with open("generic_trace.txt", "w") as f:
                traceback.print_exc(file=f)
            raise e

    def test_logic_error_handling(self):
        print("\n[Bakery] Testing Logic Error...")
        with self.assertRaises(ValueError):
            # Try to bake too much (requires 202 flour, have 80)
            self.engine.run_process("bake", quantity=101)
        print("   -> Caught Value Error as expected.")

    def test_contract_violation_read(self):
        print("\n[Bakery] Testing Read Violation...")
        # Rust Engine raises PermissionError (built-in) for illegal access
        with self.assertRaises((ContractViolationError, PermissionError)) as cm:
            self.engine.run_process("bad_read")
        self.assertIn("Illegal Read", str(cm.exception))
        print("   -> Caught Read Violation.")

    def test_contract_violation_write(self):
        print("\n[Bakery] Testing Write Violation...")
        with self.assertRaises((ContractViolationError, PermissionError)) as cm:
            self.engine.run_process("bad_write")
        self.assertIn("Illegal Write", str(cm.exception))
        print("   -> Caught Write Violation.")

if __name__ == "__main__":
    unittest.main()
