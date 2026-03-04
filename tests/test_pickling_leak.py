import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dataclasses import dataclass
from theus.guards import ContextGuard
import theus_core

# Mocking the Engine structure
class MockEngine:
    def execute_process_async(self, func_name, target_func, tx):
        pass

@dataclass
class DummyDomain:
    my_data: dict

def main():
    print("--- INTEGRATED TEST: TRANSACTION PICKLING LEAK ---")
    
    # 1. Create a Fake Transaction
    engine = theus_core.TheusEngine()
    tx = theus_core.Transaction(engine, write_timeout_ms=1000)
    print(f"1. Created Transaction: {tx} (Picklable: False)")
    
    try:
        import pickle
        pickle.dumps(tx)
    except Exception as e:
        print(f"   [Verify Pickling] Expected failure: {e}")

    # 2. Simulate User Data
    user_domain = DummyDomain(my_data={"some_key": "some_value"})
    
    # Let's see what happened before refactoring (public properties)
    print("\n--- BEFORE REFACTORING (Public Properties) ---")
    class OldContextGuard:
        def __init__(self, target, tx):
            self.target = target
            self.transaction = tx
            
        def __getattr__(self, name):
            if name in ("target", "transaction"):
                return object.__getattribute__(self, name)
            return getattr(self.target, name)
            
        def __dir__(self):
            return dir(self.target) + ["transaction", "target"]
            
    old_guard = OldContextGuard(user_domain, tx)
    
    # When Python (or Pydantic/Rust) iterates or tries to copy the guard, it looks at __dict__ or attributes.
    print(f"Has 'transaction' attr: {hasattr(old_guard, 'transaction')}")
    
    # Why did it work before?
    # Because PyO3 (Rust) State serialization uses python dictionary unwrapping?
    # Or maybe because Theus Core treats ContextGuard via __dict__?
    # Actually, in Theus Core (zones.rs), it uses PyAny::getattr("to_dict") or PyDict.
    
    # Let's inspect the New ContextGuard
    print("\n--- AFTER REFACTORING (Protected Properties) ---")
    new_guard = ContextGuard(target_obj=user_domain, allowed_inputs={"domain", "my_data"}, allowed_outputs={"domain", "my_data"}, path_prefix="", transaction=tx, strict_guards=False, process_name="test")
    
    print(f"Has '_transaction' attr: {hasattr(new_guard, '_transaction')}")
    # Removed hasattr('transaction') because it raises PermissionError in Theus v3
    
    # If a user does: ctx.domain.my_data["nested"] = ctx.domain
    # The `ContextGuard.__setattr__` unwraps the Top-Level ContextGuard.
    print("\n--- SIMULATING USER SETTING NESTED GUARD ---")
    try:
        # User process does:
        new_guard.my_data["nested"] = new_guard
        print("Set nested guard SUCCESS")
    except Exception as e:
        print(f"Set nested guard FAILED: {e}")
        
    print(f"Type of my_data['nested']: {type(new_guard.my_data['nested'])}")
    
    # Now, if we try to extract this dictionary (like Rust does natively on the raw dict)
    extracted_data = user_domain.my_data
    print(f"Extracted Data: {extracted_data}")
    
    print("\n--- SIMULATING DEEPCOPY (Rust Failure) ---")
    import copy
    try:
        copy.deepcopy(extracted_data)
        print("Deepcopy SUCCESS! (Weird, shouldn't happen)")
    except Exception as e:
        print(f"Deepcopy FAILED: {type(e).__name__}: {e}")
        print("CONCLUSION: This matches the user's error trace exactly!")

if __name__ == "__main__":
    main()
