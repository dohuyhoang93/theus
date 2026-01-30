import asyncio
import unittest
from typing import Dict, Any
from pydantic import BaseModel, Field, ValidationError

import theus.engine
import theus.contracts
from theus_core import SchemaViolationError

# --- Constants & Schema ---


# Use Pydantic BaseModel for automatic validation hooks
class BankAccount(BaseModel):
    # Constraint: Balance cannot be negative
    balance: int = Field(default=100, ge=0)


class BankSystem(BaseModel):
    domain: BankAccount = Field(default_factory=BankAccount)
    global_ctx: Dict[str, Any] = Field(default_factory=dict)


# --- Process Definition ---


@theus.contracts.process(inputs=["domain.balance"], outputs=["domain.balance"])
def withdraw_money(ctx, amount: int):
    # Logic: Simply subtracts. Does not check bounds from business logic perspective.
    # Reliance is on Schema Enforcement.
    ctx.domain.balance -= amount
    return "Process Completed"


# --- Integration Test Class ---


class TestSchemaGatekeeper(unittest.TestCase):
    def test_cas_schema_enforcement(self):
        """
        Integration Test to verify that Explicit CAS (compare_and_swap)
        respects Pydantic Schema constraints.
        """
        asyncio.run(self._run_async_test())

    async def _run_async_test(self):
        # 1. Setup
        print("\n[Test] Initializing Engine with BankSystem Schema...")
        ctx = BankSystem(domain=BankAccount(balance=100))
        engine = theus.engine.TheusEngine(ctx, strict_mode=True)

        # Explicitly ensure Schema is registered (using new engine API)
        engine.set_schema(BankSystem)
        engine.register(withdraw_money)

        # 2. Verify Initial State
        domain_data = engine.state.data["domain"]
        initial_balance = getattr(domain_data, "balance", None)
        self.assertEqual(initial_balance, 100, "Initial balance should be 100")

        # 3. Execute Invalid Transaction (Withdraw 200 -> -100)
        print("[Test] Attempting invalid withdrawal (200)...")
        with self.assertRaises(SchemaViolationError) as cm:
            await engine.execute("withdraw_money", amount=200)

        print(f"[Test] Successfully caught expected error: {cm.exception}")

        # 4. Verify Rollback (Zero Trust)
        print("[Test] Verifying State Integrity (Rollback)...")
        # Refresh state view
        current_data = engine.state.data["domain"]
        current_balance = getattr(current_data, "balance", None)

        # It must remain 100 (Object) and NOT be corrupted to -100 (Dict)
        self.assertEqual(current_balance, 100, "State should be rolled back to 100")
        self.assertIsInstance(
            current_data, BankAccount, "State should remain a Pydantic Model"
        )

        print("[Test] ✅ CAS Schema Gatekeeper Verified!")


if __name__ == "__main__":
    unittest.main()
