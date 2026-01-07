import unittest
from theus import BaseGlobalContext, BaseDomainContext, BaseSystemContext, TheusEngine, process, ContractViolationError
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class MockGlobal(BaseGlobalContext):
    pass

@dataclass
class MockDomain(BaseDomainContext):
    data_list: List[int] = field(default_factory=lambda: [1, 2, 3])
    data_dict: Dict[str, int] = field(default_factory=lambda: {"a": 1})
    nested_list: List[List[int]] = field(default_factory=lambda: [[100], [200]])

@dataclass
class MockSystem(BaseSystemContext):
    pass

# --- Processes ---

@process(inputs=['domain_ctx.data_list'], outputs=[])
def p_illegal_append(ctx):
    ctx.domain_ctx.data_list.append(4)

@process(inputs=['domain_ctx.data_list'], outputs=[])
def p_illegal_setitem(ctx):
    ctx.domain_ctx.data_list[0] = 99

@process(inputs=['domain_ctx.data_dict'], outputs=[])
def p_illegal_dict_set(ctx):
    ctx.domain_ctx.data_dict["b"] = 2

@process(inputs=['domain_ctx.data_list'], outputs=['domain_ctx.data_list'])
def p_legal_append(ctx):
    ctx.domain_ctx.data_list.append(5)

@process(inputs=['domain_ctx.nested_list'], outputs=[])
def p_illegal_nested_modify(ctx):
    # This should return a FrozenList inside a FrozenList
    inner_list = ctx.domain_ctx.nested_list[0]
    inner_list.append(101)

# --- Tests ---

class TestFrozenWrappers(unittest.TestCase):
    def setUp(self):
        glob = MockGlobal()
        self.dom = MockDomain()
        self.sys = MockSystem(global_ctx=glob, domain_ctx=self.dom)
        self.engine = TheusEngine(self.sys)
        
        self.engine.register_process("p_illegal_append", p_illegal_append)
        self.engine.register_process("p_illegal_setitem", p_illegal_setitem)
        self.engine.register_process("p_legal_append", p_legal_append)
        self.engine.register_process("p_illegal_dict_set", p_illegal_dict_set)
        self.engine.register_process("p_illegal_nested_modify", p_illegal_nested_modify)

    def test_frozen_list_append(self):
        with self.assertRaises(ContractViolationError) as cm:
            self.engine.run_process("p_illegal_append")
        self.assertIn("Immutable Violation", str(cm.exception))

    def test_frozen_list_setitem(self):
        with self.assertRaises(ContractViolationError) as cm:
            self.engine.run_process("p_illegal_setitem")
        self.assertIn("Immutable Violation", str(cm.exception))

    def test_frozen_dict_setitem(self):
        with self.assertRaises(ContractViolationError) as cm:
            self.engine.run_process("p_illegal_dict_set")
        self.assertIn("Immutable Violation", str(cm.exception))

    def test_nested_freeze(self):
        # Accessing nested list should arguably return frozen list too
        with self.assertRaises(ContractViolationError) as cm:
            self.engine.run_process("p_illegal_nested_modify")
        self.assertIn("Immutable Violation", str(cm.exception))

    def test_legal_modification(self):
        # Should work because declared in outputs
        self.engine.run_process("p_legal_append")
        self.assertEqual(self.dom.data_list, [1, 2, 3, 5])

if __name__ == "__main__":
    unittest.main()
