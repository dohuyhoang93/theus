import unittest
from unittest.mock import MagicMock
from theus.validator import AuditValidator
from theus.audit import AuditSystem, AuditRecipe, AuditLevel, AuditBlockError, AuditStopError, AuditWarning

class TestValidatorUnit(unittest.TestCase):

    def setUp(self):
        # Mock Definitions
        self.definitions = {
            "p_test": {
                "inputs": [
                    {"field": "age", "min": 18, "message": "Too young"},
                    {"field": "code", "regex": r"^[A-Z]{3}$"}
                ],
                "outputs": [
                    {"field": "domain.score", "max": 100},
                    {"field": "domain.items", "max_len": 3}
                ]
            }
        }
        
        # Real Audit System (backed by Rust logic if possible, or Mock for unit speed)
        # Using Real AuditSystem requires Theus Core.
        # Let's use Real to verify integration with Rust Counter.
        self.recipe = AuditRecipe(level=AuditLevel.Block, threshold_max=2)
        self.audit = AuditSystem(self.recipe)
        
        self.validator = AuditValidator(self.definitions, self.audit)

    def test_input_gate_success(self):
        """Tier 1: Valid Inputs."""
        # Age 20 > 18. Code ABC matches regex.
        kwargs = {"age": 20, "code": "ABC"}
        self.validator.validate_inputs("p_test", kwargs)
        
        count = self.audit.get_count("p_test:input:age")
        self.assertEqual(count, 0)

    def test_input_gate_fail_min(self):
        """Tier 2: Warning (Under Min)."""
        # Age 10 < 18.
        kwargs = {"age": 10, "code": "ABC"}
        
        # 1st fail -> Log but no block (threshold=2)
        self.validator.validate_inputs("p_test", kwargs)
        
        count = self.audit.get_count("p_test:input:age")
        self.assertEqual(count, 1)

    def test_input_gate_fail_regex(self):
        """Regex Failure."""
        kwargs = {"age": 20, "code": "abc"} # Lowercase
        self.validator.validate_inputs("p_test", kwargs)
        self.assertEqual(self.audit.get_count("p_test:input:code"), 1)

    def test_output_gate_fail_max(self):
        """Output Max Validation."""
        pending_data = {"domain": {"score": 150}} # > 100
        self.validator.validate_outputs("p_test", pending_data)
        self.assertEqual(self.audit.get_count("p_test:output:domain.score"), 1)

    def test_output_gate_fail_maxlen(self):
        """Output MaxLen Validation."""
        pending_data = {"domain": {"items": [1, 2, 3, 4]}} # len 4 > 3
        self.validator.validate_outputs("p_test", pending_data)
        self.assertEqual(self.audit.get_count("p_test:output:domain.items"), 1)

    def test_tier_3_block(self):
        """Tier 3: Blocking after threshold."""
        kwargs = {"age": 5} # Fail
        
        # Fail 1
        self.validator.validate_inputs("p_test", kwargs)
        # Fail 2
        self.validator.validate_inputs("p_test", kwargs)
        
        # Fail 3 -> Block
        with self.assertRaises(AuditBlockError):
            self.validator.validate_inputs("p_test", kwargs)

if __name__ == "__main__":
    unittest.main()
