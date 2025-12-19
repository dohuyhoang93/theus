from dataclasses import dataclass
from theus.delta import Transaction

class FakeTensor:
    """Simulates a Tensor/Numpy array (No __dict__, or special behavior)"""
    __slots__ = ['data'] # No __dict__
    def __init__(self, data):
        self.data = data
    
    def __copy__(self):
        return FakeTensor(self.data[:]) # Deep-ish copy of data
    
    def __repr__(self):
        return f"Tensor({self.data})"

@dataclass
class Context:
    tensor: FakeTensor

def test_tensor_flow():
    print("--- TESTING TENSOR TRANSACTION ---")
    
    # 1. Setup
    original = FakeTensor([1, 2, 3])
    ctx = Context(tensor=original)
    
    print(f"Original: {ctx.tensor} ID={id(ctx.tensor)}")
    
    # 2. Start Transaction
    tx = Transaction(ctx)
    
    # 3. Get Shadow (Triggered by Output declaration in real flow)
    print(">> Creating Shadow...")
    shadow = tx.get_shadow(ctx.tensor)
    print(f"Shadow:   {shadow} ID={id(shadow)}")
    
    # 4. Modify Shadow (The Process logic)
    print(">> Modifying Shadow ([0] = 99)...")
    shadow.data[0] = 99
    print(f"Shadow Now: {shadow}")
    print(f"Original:   {ctx.tensor} (Should be unchanged if copy worked)")
    
    # 5. Commit
    print(">> Committing...")
    tx.commit()
    
    # 6. Verify Result
    print(f"Final Original: {ctx.tensor}")
    
    if ctx.tensor.data[0] == 99:
        print("✅ SUCCESS: Tensor updated!")
    else:
        print("❌ FAILURE: Tensor update LOST (Original still old value)")

if __name__ == "__main__":
    test_tensor_flow()
