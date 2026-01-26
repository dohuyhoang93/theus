
import pytest
import time
from theus_core import ConflictManager

# TDD: Advanced Conflict Resolution Features (v3.3)
# These features were identified as "Missing Tests" in the Audit Report.

class TestConflictManager:
    
    def test_exponential_backoff(self):
        """
        Verify that repeated conflicts result in exponentially increasing wait times.
        Formula: base * 2^(attempts-1) * jitter
        """
        # Config: max_retries=10, base=10ms
        cm = ConflictManager(max_retries=10, base_backoff_ms=10)
        key = "resource_A"
        
        waits = []
        for i in range(1, 5):
            decision = cm.report_conflict(key)
            assert decision.should_retry is True
            waits.append(decision.wait_ms)
            
        print(f"Backoff Trend: {waits}")
        
        # Verify Trend: Should roughly double each time
        # Due to jitter (0.8-1.2), strict doubling isn't guaranteed, but it should increase.
        # 1st jump: 10 -> ~20
        # 2nd jump: 20 -> ~40
        for i in range(len(waits) - 1):
            assert waits[i+1] > waits[i], f"Backoff did not increase: {waits[i]} -> {waits[i+1]}"
            
        # Verify Range (approx)
        # Attempt 1 (prev 0): 10 * 2^0 = 10. Jitter [8, 12]
        # Attempt 4 (prev 3): 10 * 2^3 = 80. Jitter [64, 96]
        assert 8 <= waits[0] <= 12
        assert 50 <= waits[-1] <= 110 # Loose bound for attempt 4

    def test_vip_locking_mechanic(self):
        """
        Verify that after max_retries, a process escalates to VIP status.
        And other processes are blocked by the VIP.
        """
        MAX_RETRIES = 5
        cm = ConflictManager(max_retries=MAX_RETRIES, base_backoff_ms=2)
        
        victim = "process_victim"
        bully = "process_bully"
        
        # 1. Victim fails MAX_RETRIES times
        for _ in range(MAX_RETRIES):
            decision = cm.report_conflict(victim)
            assert decision.should_retry is True
            
        # 2. Next failure should TRIGGER VIP
        # Logic in Rust: If *count >= max_retries AND vip is None -> Become VIP
        decision_vip = cm.report_conflict(victim)
        
        assert decision_vip.should_retry is True
        assert decision_vip.wait_ms <= 5, "VIP should have minimal wait time (priority)"
        
        # 3. Verify VIP Status using side-effect: Blocking others
        # Now 'victim' is VIP. 'bully' should be blocked.
        
        # Check is_blocked
        assert cm.is_blocked(bully) is True, "Bully should be blocked by Victim's VIP status"
        assert cm.is_blocked(victim) is False, "Victim should NOT be blocked by itself"
        
        # 4. Success releases VIP
        cm.report_success(victim)
        assert cm.is_blocked(bully) is False, "VIP should be released after success"
        
    def test_vip_contention(self):
        """
        Verify behavior when two processes vie for VIP.
        First to hit limit gets it.
        """
        cm = ConflictManager(max_retries=2, base_backoff_ms=1)
        p1 = "p1"
        p2 = "p2"
        
        # P1 fails 2 times
        cm.report_conflict(p1)
        cm.report_conflict(p1)
        
        # P2 fails 2 times
        cm.report_conflict(p2)
        cm.report_conflict(p2)
        
        # Both represent attempts >= max_retries.
        
        # P1 requests -> Grants VIP
        cm.report_conflict(p1) 
        assert cm.is_blocked(p2) is True
        
        # P2 requests -> Should still Retry but with WAIT (Nice block) 
        # OR Fail? 
        # Logic: if vip != me: return Retry(true, wait=50ms)
        decision_p2 = cm.report_conflict(p2)
        assert decision_p2.should_retry is True
        assert decision_p2.wait_ms == 50, "Blocked process should endure polite wait time"
