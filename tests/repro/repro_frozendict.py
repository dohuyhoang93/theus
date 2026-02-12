
import numpy as np
import theus_core

def repro():
    engine = theus_core.TheusEngine()
    # Hydrate Heavy Zone to make state non-empty
    large_np = np.zeros(10)
    engine.compare_and_swap(0, None, {"large_array": large_np}, None)
    
    print(f"State Heavy Type: {type(engine.state.heavy)}")
    # Create Transaction using Context Manager (Critical Step)
    print("\n--- Testing Context Manager ---")
    try:
        with theus_core.Transaction(engine) as tx:
            print(f"Tx Pending Heavy Type (Init): {type(tx.pending_heavy)}")
            
            # Simulate direct write to pending_heavy (mimicking engine.py output processing)
            # engine.py: tx.pending_heavy[rest[0]] = val
            print("Writing to pending_heavy 'new_array'...")
            tx.pending_heavy["new_array"] = np.ones(5)
            
            # Simulate Read Shadowing to trigger infer_shadow_deltas
            # In real app, accessing ctx.heavy creates a shadow.
            # Here we manually invoke get_shadow to put an entry in full_path_map
            # Path must start with "heavy." to trigger heavy logic? 
            # infer_shadow_deltas iterates full_path_map.
            
            # Let's try to get a shadow for the ROOT 'heavy' zone to see if __eq__ prevents delta.
            # But we can't easily get 'heavy' object from transaction API directly?
            # We can use get_shadow on the state object?
            # Transaction.get_shadow(py, obj, path)
            # We need the object `engine.state.heavy` (FrozenDict).
            frozen_heavy = engine.state.heavy
            
            print("Creating Shadow for 'heavy' zone...")
            # Path must match what ContextGuard uses: "heavy"
            # Note: get_shadow returns the shadow.
            shadow = tx.get_shadow(frozen_heavy, "heavy")
            
            # Verify Shadow Identity
            print(f"Original ID: {id(frozen_heavy)}")
            print(f"Shadow ID:   {id(shadow)}")
            
            if id(frozen_heavy) == id(shadow):
                print("⚠️  Warning: Zero-Copy active (IDs Identical). Skipping __eq__ check.")
            else:
                print("ℹ️  IDs Differ. Checking Equality...")
                if frozen_heavy == shadow:
                    print("✅ FrozenDict.__eq__ MATCHED! (Correct)")
                else:
                    print("❌ FrozenDict.__eq__ FAILED! (This causes the bug)")

            print("Write/Update Success")
            
        print("Context Manager Exit Success (Commit Done)")
        
        # Verify Post-Commit State
        print("\n--- Verifying State Structure ---")
        new_heavy = engine.state.heavy
        keys = list(new_heavy.keys())
        print(f"State Heavy Keys: {keys}")
        
        if "heavy" in keys:
            print("❌ FAILURE: Namespace Corruption Detected! Found nested 'heavy' key.")
        elif "new_array" in keys:
             print("✅ NOTE: 'new_array' found. Commit applied.")
             
             # Check integrity
             arr = new_heavy["new_array"]
             if isinstance(arr, np.ndarray) and arr.shape == (5,):
                 print("✅ Data Integrity Verified.")
             else:
                 print(f"❌ Data Corruption: {arr}")
        else:
             print("❌ MISSING DATA: 'new_array' not found in state.")

    except Exception as e:
        print(f"CRASH in Context Manager: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    repro()
