import unittest
from theus.config import RuleSpec, AuditRecipe, ProcessRecipe
from theus.audit import ContextAuditor, AuditInterlockError, AuditWarning

class TestAuditInvestigation(unittest.TestCase):
    def setUp(self):
        # Setup specific rules for investigation
        # Rule 1: Threshold = 3. Level = A.
        self.rule_a = RuleSpec(target_field="val", condition="max", value=10, level="A", threshold=3)
        self.tracker_key = "test:val"
        self.auditor = ContextAuditor({}) # Recipe not needed for direct policy test

    def test_current_threshold_behavior(self):
        print("\n--- Investigating Threshold Logic (Limit=3) ---")
        
        # 1st Violation
        print("Violation 1:")
        self.auditor.policy._handle_violation(self.rule_a, 11, self.tracker_key)
        count = self.auditor.tracker._states[self.tracker_key].count
        print(f"-> Count: {count} (Expect Warn)")
        
        # 2nd
        print("Violation 2:")
        self.auditor.policy._handle_violation(self.rule_a, 11, self.tracker_key)
        count = self.auditor.tracker._states[self.tracker_key].count
        print(f"-> Count: {count} (Expect Warn)")
        
        # 3rd (Hit Limit)
        print("Violation 3:")
        self.auditor.policy._handle_violation(self.rule_a, 11, self.tracker_key)
        count = self.auditor.tracker._states[self.tracker_key].count
        print(f"-> Count: {count} (Expect Warn? Or Stop?) -> Current Logic: Count > Limit => Stop. 3 > 3 False.")
        
        # 4th (Exceed Limit)
        print("Violation 4:")
        try:
            self.auditor.policy._handle_violation(self.rule_a, 11, self.tracker_key)
            print("-> DID NOT STOP (Unexpected if aiming for strict limit?)")
        except AuditInterlockError as e:
            print(f"-> STOPPED: {e}")

if __name__ == '__main__':
    unittest.main()
