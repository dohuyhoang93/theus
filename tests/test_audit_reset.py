import sys
import os

# Add project root to path
# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from theus.config import AuditRecipe, ProcessRecipe, RuleSpec
from theus.audit import AuditPolicy

def test_audit_reset():
    print("=== TESTING AUDIT RESET LOGIC ===")

    # Scenario 1: reset_on_success = False (Default - Accumulate)
    print("\n--- Scenario 1: Accumulate (reset_on_success=False) ---")
    recipe1 = AuditRecipe(definitions={
        "p_test": ProcessRecipe(
            process_name="p_test",
            input_rules=[
                RuleSpec(
                    target_field="value",
                    condition="min",
                    value=10,
                    min_threshold=0,
                    max_threshold=3, # Fail on 3rd violation
                    reset_on_success=False # <--- ACCUMULATE
                )
            ]
        )
    })
    
    policy1 = AuditPolicy(recipe1)
    
    # Mock Context object
    class ctx:
        value = 0
    
    c = ctx()
    
    # Step 1: Fail (Count 1)
    c.value = 5 # < 10
    print("Step 1 (Fail): ", end="")
    policy1.evaluate("p_test", "input", c) 
    print(f"Counter: {policy1.tracker.counters.get('p_test:value:min', 0)}")

    # Step 2: Fail (Count 2)
    c.value = 5 
    print("Step 2 (Fail): ", end="")
    policy1.evaluate("p_test", "input", c)
    print(f"Counter: {policy1.tracker.counters.get('p_test:value:min', 0)}")

    # Step 3: SUCCESS (Should NOT reset)
    c.value = 15 # >= 10
    print("Step 3 (Success): ", end="")
    policy1.evaluate("p_test", "input", c)
    print(f"Counter: {policy1.tracker.counters.get('p_test:value:min', 0)} (Expect 2)")

    # Step 4: Fail (Count 3 -> TRIGGER)
    c.value = 5
    print("Step 4 (Fail): ", end="")
    try:
        policy1.evaluate("p_test", "input", c)
        print("DID NOT TRIGGER!")
    except Exception as e:
        print(f"TRIGGERED: {e}")
    print(f"Counter: {policy1.tracker.counters.get('p_test:value:min', 0)}")


    # Scenario 2: reset_on_success = True (Forgive)
    print("\n--- Scenario 2: Forgive (reset_on_success=True) ---")
    recipe2 = AuditRecipe(definitions={
        "p_test": ProcessRecipe(
            process_name="p_test",
            input_rules=[
                RuleSpec(
                    target_field="value",
                    condition="min",
                    value=10,
                    min_threshold=0,
                    max_threshold=3,
                    reset_on_success=True # <--- RESET
                )
            ]
        )
    })
    
    policy2 = AuditPolicy(recipe2)
    
    # Step 1: Fail (Count 1)
    c.value = 5
    print("Step 1 (Fail): ", end="")
    policy2.evaluate("p_test", "input", c)
    print(f"Counter: {policy2.tracker.counters.get('p_test:value:min', 0)}")

    # Step 2: Fail (Count 2)
    c.value = 5
    print("Step 2 (Fail): ", end="")
    policy2.evaluate("p_test", "input", c)
    print(f"Counter: {policy2.tracker.counters.get('p_test:value:min', 0)}")

    # Step 3: SUCCESS (Should RESET to 0)
    c.value = 15
    print("Step 3 (Success): ", end="")
    policy2.evaluate("p_test", "input", c)
    print(f"Counter: {policy2.tracker.counters.get('p_test:value:min', 0)} (Expect 0)")

    # Step 4: Fail (Count 1)
    c.value = 5
    print("Step 4 (Fail): ", end="")
    try:
        policy2.evaluate("p_test", "input", c)
        print(f"Counter: {policy2.tracker.counters.get('p_test:value:min', 0)} (Expect 1)")
    except Exception as e:
        print(f"UNEXPECTED TRIGGER: {e}")

if __name__ == "__main__":
    test_audit_reset()
