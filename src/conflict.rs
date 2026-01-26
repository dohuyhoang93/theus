use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use rand::Rng;

#[pyclass(module = "theus_core")]
#[derive(Clone, Debug)]
pub struct RetryDecision {
    #[pyo3(get)]
    pub should_retry: bool,
    #[pyo3(get)]
    pub wait_ms: u64,
}

#[pymethods]
impl RetryDecision {
    fn __repr__(&self) -> String {
        format!("RetryDecision(retry={}, wait={}ms)", self.should_retry, self.wait_ms)
    }
}

/// Manages conflict resolution policies (Backoff, Priority)
#[pyclass(module = "theus_core")]
pub struct ConflictManager {
    // track failures: process_name -> count
    failures: Arc<Mutex<HashMap<String, u32>>>,
    // v3.3: Priority Ticket (VIP Holder)
    vip_holder: Arc<Mutex<Option<String>>>,
    max_retries: u32,
    base_backoff_ms: u64,
}

#[pymethods]
impl ConflictManager {
    #[new]
    #[pyo3(signature = (max_retries=5, base_backoff_ms=2))]
    pub fn new(max_retries: u32, base_backoff_ms: u64) -> Self {
        ConflictManager {
            failures: Arc::new(Mutex::new(HashMap::new())),
            vip_holder: Arc::new(Mutex::new(None)),
            max_retries,
            base_backoff_ms,
        }
    }

    /// Report a conflict failure for a process/key.
    /// Returns a decision on whether to retry and how long to wait.
    pub fn report_conflict(&self, key: String) -> RetryDecision {
        let mut map = self.failures.lock().unwrap();
        let count = map.entry(key.clone()).or_insert(0);
        
        let mut vip_lock = self.vip_holder.lock().unwrap();
        
        // Check if I am blocked by another VIP
        if let Some(ref current_vip) = *vip_lock {
            if current_vip != &key {
                // I am blocked by a VIP. Wait nicely.
                return RetryDecision { should_retry: true, wait_ms: 50 }; // 50ms snooze
            }
        }
        
        if *count >= self.max_retries {
            // Check if we should escalate to VIP instead of failing?
            // If I failed 5 times, I become VIP.
            // Reset counter partly to allow execution attempt as VIP?
            // Or just grant VIP and return retry?
            if vip_lock.is_none() {
                *vip_lock = Some(key.clone());
                 // Reset counter to give VIP unlimited attempts? Or just access?
                 // Let's reset counter to 0 so it doesn't fail immediately max limit check.
                 // *count = 0; 
                 // Return immediate retry with VIP status.
                 return RetryDecision { should_retry: true, wait_ms: 1 };
            } else if *vip_lock == Some(key.clone()) {
                 // I am already VIP. Keep trying.
                 // Don't fail me.
                 return RetryDecision { should_retry: true, wait_ms: 1 };
            } else {
                 // VIP occupied by someone else, and I hit limit.
                 // Give up.
                 return RetryDecision { should_retry: false, wait_ms: 0 };
            }
        }

        *count += 1;
        let attempts = *count;
        
        // Calculate Exponential Backoff with Jitter
        // delay = base * 2^(attempts-1)
        let mut delay = self.base_backoff_ms * (1 << (attempts - 1).min(10)); 
        
        // Add random Jitter +/- 20%
        let mut rng = rand::thread_rng();
        let jitter = rng.gen_range(0.8..1.2);
        delay = (delay as f64 * jitter) as u64;
        
        RetryDecision { 
            should_retry: true, 
            wait_ms: delay 
        }
    }

    /// Report success to reset counters.
    pub fn report_success(&self, key: String) {
        let mut map = self.failures.lock().unwrap();
        map.remove(&key);
        
        // Release VIP if held
        let mut vip_lock = self.vip_holder.lock().unwrap();
        if *vip_lock == Some(key) {
            *vip_lock = None;
        }
    }
    
    /// Get current failure count (Internal Diagnostic)
    pub fn get_failure_count(&self, key: String) -> u32 {
        let map = self.failures.lock().unwrap();
        *map.get(&key).unwrap_or(&0)
    }
    
    /// Check if action is blocked by VIP
    pub fn is_blocked(&self, requester: Option<String>) -> bool {
        let vip = self.vip_holder.lock().unwrap();
        if let Some(ref holder) = *vip {
            if let Some(req) = requester {
                return holder != &req;
            }
            return true; // Anonymous requests blocked by VIP
        }
        false
    }
}
