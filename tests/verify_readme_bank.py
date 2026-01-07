from dataclasses import dataclass, field
from theus.context import BaseSystemContext, BaseGlobalContext, BaseDomainContext
from theus.contracts import process
from theus.engine import TheusEngine

@dataclass
class BankDomain(BaseDomainContext):
    # DATA ZONE: Persistent Assets
    accounts: dict = field(default_factory=dict) # {user_id: balance}
    total_reserves: int = 1_000_000
    
    # SIGNAL ZONE: Control Flow
    sig_fraud_detected: bool = False

@dataclass
class BankSystem(BaseSystemContext):
    # Define concrete types for defaults
    domain_ctx: BankDomain = field(default_factory=BankDomain)
    global_ctx: BaseGlobalContext = field(default_factory=BaseGlobalContext)

@process(
    # STRICT CONTRACT
    inputs=['domain_ctx.accounts'],
    outputs=['domain_ctx.accounts', 'domain_ctx.total_reserves', 'domain_ctx.sig_fraud_detected'],
    errors=['ValueError']
)
def transfer(ctx, from_user: str, to_user: str, amount: int):
    # 1. Input Validation
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    # 2. Business Logic (Operating on Shadow Copies)
    sender_bal = ctx.domain_ctx.accounts.get(from_user, 0)
    
    if sender_bal < amount:
        # Trigger Signal
        ctx.domain_ctx.sig_fraud_detected = True
        return "Failed: Insufficient Funds"

    # 3. Mutation (Optimistic Write)
    ctx.domain_ctx.accounts[from_user] -= amount
    ctx.domain_ctx.accounts[to_user] = ctx.domain_ctx.accounts.get(to_user, 0) + amount
    
    return "Success"

# Run with Safety
if __name__ == "__main__":
    # Setup Data
    sys_ctx = BankSystem()
    sys_ctx.domain_ctx.accounts = {"Alice": 1000, "Bob": 0}

    # Initialize Engine
    engine = TheusEngine(sys_ctx, strict_mode=True)

    engine.register_process("transfer", transfer)

    # Execute
    print("Executing transfer...")
    result = engine.run_process("transfer", from_user="Alice", to_user="Bob", amount=500)

    print(f"Result: {result}")
    print(f"Alice: {sys_ctx.domain_ctx.accounts['Alice']}") # 500
    
    assert result == "Success"
    assert sys_ctx.domain_ctx.accounts['Alice'] == 500
    assert sys_ctx.domain_ctx.accounts['Bob'] == 500
    print("✅ Bank Example Verified!")
