import asyncio
import unittest
import os
from theus import TheusEngine
from theus.contracts import process, SemanticType
from theus_core import AuditBlockError, AuditStopError, AuditWarning

# Mock Process
@process(inputs=['age', 'server'], outputs=['domain.score'])
async def p_signup(ctx, age, server):
    return 100 # Returns score

class TestAuditIntegration(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        # Configuration Dictionary
        self.recipe = {
            "audit": {
                "threshold_max": 2, # Block after 2 attempts
                "reset_on_success": True
            },
            "process_recipes": {
                "p_signup": {
                    "inputs": [
                        # Tier 1/2/3 Target
                        {"field": "age", "min": 18, "message": "Too young"},
                        # Tier 4 Target (Safety Stop)
                        {"field": "server", "regex": r"^PROD.*", "level": "S", "message": "Invalid Server"} 
                        # Note: currently Level in yaml isn't parsed into Logic yet (Validator uses default or AuditSystem level?)
                        # Validator._check_rule currently just calls log_fail. 
                        # AuditSystem decides action based on global level.
                        # Wait, AuditSystem level is GLOBAL?
                        # Yes, AuditRecipe is global for the system instance.
                        # If we want Per-Rule Level (S/A/B/C), Validator needs to override?
                        # Implementation Gaps:
                        # Validator.py doesn't handle per-rule level yet. It just calls log_fail.
                        # AuditSystem (Rust) handles logic based on ITS recipe.
                        # So for now, we only test GLOBAL Level enforcement unless we update Validator.
                    ],
                    "outputs": [
                        {"field": "domain.score", "max": 200}
                    ]
                }
            }
        }
        
        # Init Engine
        self.engine = TheusEngine(
            context={"domain": {"score": 0}},
            strict_guards=True,
            audit_recipe=self.recipe
        )
        self.engine.register(p_signup)

    async def test_tier_1_valid(self):
        """Tier 1: Valid Execution"""
        print("\n[INTEGRATION] Tier 1: Valid")
        res = await self.engine.execute(p_signup, age=25, server="PROD-1")
        self.assertEqual(res, 100)
        print("    [+] Success")

    async def test_tier_3_block_flow(self):
        """Tier 3: Blocking Flow (Global Level B)"""
        print("\n[INTEGRATION] Tier 3: Block Flow")
        
        # Fail 1
        print("    [+] Trigger Fail 1")
        await self.engine.execute(p_signup, age=10, server="PROD-1") # Age < 18
        
        # Fail 2
        print("    [+] Trigger Fail 2")
        await self.engine.execute(p_signup, age=10, server="PROD-1") 
        
        # Fail 3 -> BLOCK
        print("    [!] Trigger Fail 3 (Expect Block)")
        with self.assertRaises(AuditBlockError):
            await self.engine.execute(p_signup, age=10, server="PROD-1")
            
        print("    [+] BLOCKED Successfully via Rust Core!")

if __name__ == "__main__":
    unittest.main()
