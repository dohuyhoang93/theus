import asyncio
import sys
import unittest
from theus import TheusEngine
from theus.contracts import process, SemanticType
from theus.audit import AuditSystem, AuditRecipe, AuditLevel, AuditBlockError, AuditStopError, AuditWarning

# Mock Processes
@process(outputs=['result'])
async def p_action(ctx):
    return 1

class TestAuditBoundaries(unittest.IsolatedAsyncioTestCase):
    
    async def test_tier_1_standard(self):
        """Tier 1: Standard Case - Validation Success."""
        print("\n[TIER 1] Standard Case (Happy Path)")
        
        # Recpie: Block at 3. Level Block.
        recipe = AuditRecipe(level=AuditLevel.Block, threshold_max=3)
        audit = AuditSystem(recipe)
        
        # Simulate Success
        audit.log_success("p_action")
        
        # Verify Count Reset? (Default reset_on_success=True)
        count = audit.get_count("p_action")
        print(f"    [+] Count after success: {count}")
        self.assertEqual(count, 0)
        print("    [+] PASS: Tier 1 Standard")

    async def test_tier_2_related_warning(self):
        """Tier 2: Related Case - Warning Zone (Min Threshold)."""
        print("\n[TIER 2] Warning Zone (Related)")
        
        # Recipe: Warn at 1, Block at 5
        recipe = AuditRecipe(level=AuditLevel.Block, threshold_max=5, threshold_min=1)
        audit = AuditSystem(recipe)
        
        # Trigger 1st Fail
        with self.assertWarns(AuditWarning):
            # This should emit Warning but NOT raise Exception
            audit.log_fail("p_warning")
        
        count = audit.get_count("p_warning")
        print(f"    [+] Count after 1 fail: {count} (Warning Emitted)")
        self.assertEqual(count, 1)
        print("    [+] PASS: Tier 2 Warning/Related")

    async def test_tier_3_edge_block(self):
        """Tier 3: Edge Case - Threshold Block (Level B)."""
        print("\n[TIER 3] Edge Case (Blocking)")
        
        # Recipe: Block at MAX=2
        recipe = AuditRecipe(level=AuditLevel.Block, threshold_max=2)
        audit = AuditSystem(recipe)
        
        # Fail 1
        audit.log_fail("p_edge")
        # Fail 2
        audit.log_fail("p_edge")
        print("    [+] Reached Max Threshold (2)")
        
        # Fail 3 -> BLOCK
        with self.assertRaises(AuditBlockError):
            print("    [!] Triggering 3rd Fail (Should Block)...")
            audit.log_fail("p_edge")
            
        print("    [+] PASS: Tier 3 Blocked successfully")

    async def test_tier_4_conflict_stop(self):
        """Tier 4: Conflict Case - Safety Stop (Level S)."""
        print("\n[TIER 4] Conflict Case (Safety Stop)")
        
        # Recipe: Level S (Immediate Stop)
        recipe = AuditRecipe(level=AuditLevel.Stop, threshold_max=5) # Max irrelevant for Level S?
        audit = AuditSystem(recipe)
        
        # Fail 1 -> STOP IMMEDIATE
        with self.assertRaises(AuditStopError):
            print("    [!] Triggering 1st Fail (Safety Stop)...")
            audit.log_fail("p_stop")
            
        print("    [+] PASS: Tier 4 Safety Stop triggered immediate halt")

if __name__ == "__main__":
    unittest.main()
