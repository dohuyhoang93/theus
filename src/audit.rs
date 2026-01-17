use pyo3::prelude::*;

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

// ============================================================================
// Exception Types
// ============================================================================

pyo3::create_exception!(theus_core, AuditBlockError, pyo3::exceptions::PyRuntimeError);
pyo3::create_exception!(theus_core, AuditAbortError, pyo3::exceptions::PyRuntimeError);
pyo3::create_exception!(theus_core, AuditStopError, pyo3::exceptions::PyRuntimeError);
pyo3::create_exception!(theus_core, AuditWarning, pyo3::exceptions::PyUserWarning);

// ============================================================================
// AuditLevel Enum (S/A/B/C)
// ============================================================================

/// Audit Level per MIGRATION_AUDIT.md
/// - S (Stop): Immediate halt on first failure
/// - A (Abort): Cancel current operation, allow retry
/// - B (Block): Block after threshold exceeded
/// - C (Count): Count only, never block
#[pyclass(module = "theus_core", eq, eq_int)]
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum AuditLevel {
    Stop = 0,   // Immediate halt
    Abort = 1,  // Cancel operation
    Block = 2,  // Block after threshold
    Count = 3,  // Count only
}

// ============================================================================
// Ring Buffer Entry (Immutable)
// ============================================================================

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct AuditLogEntry {
    #[pyo3(get)]
    pub timestamp: f64,
    #[pyo3(get)]
    pub key: String,
    #[pyo3(get)]
    pub message: String,
}

#[pymethods]
impl AuditLogEntry {
    fn __str__(&self) -> String {
        format!("[{}] {}: {}", self.timestamp, self.key, self.message)
    }
}

// ============================================================================
// Ring Buffer (Append-Only, Fixed Capacity)
// ============================================================================

struct RingBuffer {
    buffer: Vec<AuditLogEntry>,
    capacity: usize,
    write_pos: usize,
    count: usize,
}

impl RingBuffer {
    fn new(capacity: usize) -> Self {
        RingBuffer {
            buffer: Vec::with_capacity(capacity),
            capacity,
            write_pos: 0,
            count: 0,
        }
    }

    fn push(&mut self, entry: AuditLogEntry) {
        if self.buffer.len() < self.capacity {
            self.buffer.push(entry);
        } else {
            self.buffer[self.write_pos] = entry;
        }
        self.write_pos = (self.write_pos + 1) % self.capacity;
        self.count += 1;
    }

    fn get_all(&self) -> Vec<AuditLogEntry> {
        if self.buffer.len() < self.capacity {
            // Not yet wrapped around
            self.buffer.clone()
        } else {
            // Wrapped - return in order from oldest to newest
            let mut result = Vec::with_capacity(self.capacity);
            for i in 0..self.capacity {
                let idx = (self.write_pos + i) % self.capacity;
                result.push(self.buffer[idx].clone());
            }
            result
        }
    }

    fn len(&self) -> usize {
        self.buffer.len()
    }
}

// ============================================================================
// AuditRecipe (Enhanced with Level and Dual Thresholds)
// ============================================================================

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct AuditRecipe {
    #[pyo3(get, set)]
    pub level: AuditLevel,
    #[pyo3(get, set)]
    pub threshold_max: u32,
    #[pyo3(get, set)]
    pub threshold_min: u32,  // Warning threshold
    #[pyo3(get, set)]
    pub reset_on_success: bool,
}

#[pymethods]
impl AuditRecipe {
    #[new]
    #[pyo3(signature = (level=None, threshold_max=3, threshold_min=0, reset_on_success=true))]
    fn new(level: Option<AuditLevel>, threshold_max: u32, threshold_min: u32, reset_on_success: bool) -> Self {
        AuditRecipe {
            level: level.unwrap_or(AuditLevel::Block),
            threshold_max,
            threshold_min,
            reset_on_success,
        }
    }
}

// ============================================================================
// AuditSystem (Enhanced)
// ============================================================================

#[pyclass(module = "theus_core", subclass)]
pub struct AuditSystem {
    recipe: AuditRecipe,
    counts: HashMap<String, u32>,
    ring_buffer: Arc<Mutex<RingBuffer>>,
}

#[pymethods]
impl AuditSystem {
    #[new]
    #[pyo3(signature = (recipe=None, capacity=1000))]
    fn new(recipe: Option<AuditRecipe>, capacity: usize) -> Self {
        let r = recipe.unwrap_or(AuditRecipe {
            level: AuditLevel::Block,
            threshold_max: 3,
            threshold_min: 0,
            reset_on_success: true,
        });
        
        AuditSystem {
            recipe: r,
            counts: HashMap::new(),
            ring_buffer: Arc::new(Mutex::new(RingBuffer::new(capacity))),
        }
    }

    /// Log a failure event. Behavior depends on AuditLevel.
    pub fn log_fail(&mut self, py: Python, key: String) -> PyResult<()> {
        // First: update count (mutable borrow)
        let current_count: u32 = {
            let count = self.counts.entry(key.clone()).or_insert(0);
            *count += 1;
            *count  // Copy value before releasing borrow
        };

        // Now: immutable borrows are safe
        // Log to ring buffer
        self.log_internal(&key, &format!("Fail #{}", current_count));

        let threshold_max = self.recipe.threshold_max;
        let threshold_min = self.recipe.threshold_min;

        match self.recipe.level {
            AuditLevel::Stop => {
                // S-Level: Immediate halt on first failure
                return Err(AuditStopError::new_err(format!(
                    "Audit Stop: {} triggered immediate halt", key
                )));
            }
            AuditLevel::Abort => {
                // A-Level: Abort current operation
                return Err(AuditAbortError::new_err(format!(
                    "Audit Abort: {} operation cancelled", key
                )));
            }
            AuditLevel::Block => {
                // B-Level: Block after threshold exceeded
                if current_count > threshold_max {
                    return Err(AuditBlockError::new_err(format!(
                        "Audit Blocked: {} exceeded threshold {}", 
                        key, threshold_max
                    )));
                }
                // Check warning threshold
                if threshold_min > 0 && current_count >= threshold_min {
                    // Emit warning to Python
                    pyo3::PyErr::warn_bound(
                        py,
                        &py.get_type_bound::<AuditWarning>(),
                        &format!("WARNING: Approaching threshold ({}/{})", current_count, threshold_max),
                        0
                    )?;
                    
                    // Also log to ring buffer
                    self.log_internal(&key, &format!("WARN: Approaching threshold ({}/{})", 
                        current_count, threshold_max));
                }
            }
            AuditLevel::Count => {
                // C-Level: Count only, never block
                // No action needed
            }
        }
        
        Ok(())
    }

    /// Log a success event. Resets counter if configured.
    pub fn log_success(&mut self, key: String) {
        self.log_internal(&key, "Success");
        
        if self.recipe.reset_on_success {
            self.counts.insert(key, 0);
        }
    }

    /// Get current count for a key.
    pub fn get_count(&self, key: String) -> u32 {
        *self.counts.get(&key).unwrap_or(&0)
    }

    /// Get total count across all keys.
    pub fn get_count_all(&self) -> usize {
        self.ring_buffer.lock().unwrap().count
    }

    /// Log a general event to ring buffer.
    #[pyo3(signature = (key, message))]
    pub fn log(&mut self, key: String, message: String) {
        self.log_internal(&key, &message);
    }

    /// Get all logs from ring buffer.
    pub fn get_logs(&self) -> Vec<AuditLogEntry> {
        self.ring_buffer.lock().unwrap().get_all()
    }

    /// Get number of logs in buffer.
    #[getter]
    pub fn ring_buffer_len(&self) -> usize {
        self.ring_buffer.lock().unwrap().len()
    }
}

impl AuditSystem {
    fn log_internal(&self, key: &str, message: &str) {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        let entry = AuditLogEntry {
            timestamp,
            key: key.to_string(),
            message: message.to_string(),
        };

        self.ring_buffer.lock().unwrap().push(entry);
    }
}
