import asyncio
import unittest
import logging
from dataclasses import dataclass, field
from typing import Any, Dict

import theus.engine
import theus.contracts
from theus.contracts import ContractViolationError
from theus.context import BaseSystemContext, BaseDomainContext

# We still import Audit to configure the engine, proving it is IGNORED
from theus_core import AuditRecipe, AuditLevel, AuditBlockError


# --- Setup Context ---
@dataclass
class SchemaDomain(BaseDomainContext):
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaContext(BaseSystemContext):
    domain: SchemaDomain = field(default_factory=SchemaDomain)
    global_ctx: Any = None


# --- Process Definition ---
@theus.contracts.process(inputs=["domain.allowed"], outputs=["domain.allowed"])
def contract_limit_process(ctx):
    # Violation!
    try:
        ctx.domain.data["illegal"] = "HACK"
    except:
        pass
    return "done"


class TestContractEnforcement(unittest.TestCase):
    def test_io_contract_strictness(self):
        """
        Verify IO Contract Violations are HARDBLOCKED by default
        and IGNORE Audit System Campaign Mode.
        """
        asyncio.run(self._run_contract_test())

    async def _run_contract_test(self):
        print("\n=== TEST: Core Contract Enforcement (Strict) ===")

        # Scenario: Configure AuditLevel.CAMPAIGN (Count)
        # Goal: Verify that despite Audit saying "Allow", Contract Gatekeeper says "NO".
        print("\n[Scenario] AuditLevel.CAMPAIGN (Count) vs Contract Violation")
        recipe_camp = AuditRecipe(
            threshold_max=0, reset_on_success=True, level=AuditLevel.Count
        )
        ctx = SchemaContext(domain=SchemaDomain(data={}))
        engine = theus.engine.TheusEngine(
            ctx, strict_guards=True, audit_recipe=recipe_camp
        )
        engine.register(contract_limit_process)

        # Expectation: ContractViolationError (Raised by Engine directly)
        # NOT AuditBlockError (which would come from Audit)
        # And DEFINITELY NOT Success.
        with self.assertRaises(ContractViolationError) as cm:
            print("   Executing process (expecting Strict Block)...")
            await engine.execute("contract_limit_process")

        print(f"   ✅ Caught Expected Strict Error: {cm.exception}")

        domain_obj = engine.state.data["domain"]
        if isinstance(domain_obj, dict):
            # If converted to dict
            updated_data = domain_obj.get("data", {})
        else:
            # If Dataclass/Object
            updated_data = getattr(domain_obj, "data", {})

        self.assertIsNone(updated_data.get("illegal"), "Illegal write MUST be blocked.")
        print("   ✅ Validated: Contract Enforced Strictness.")


if __name__ == "__main__":
    unittest.main()
