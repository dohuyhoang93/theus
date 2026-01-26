use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::sync::atomic::{AtomicU64, Ordering};

// =============================================================================
// SupervisorCore - Production Reference-based State Manager
// =============================================================================

/// Thread-safe wrapper for Py<PyAny>
pub struct SafePyRef(pub Py<PyAny>);

unsafe impl Send for SafePyRef {}
unsafe impl Sync for SafePyRef {}

/// Each key has its own entry with version tracking
pub struct SupervisorEntry {
    pub payload: RwLock<SafePyRef>,
    pub version: AtomicU64,
}

impl SupervisorEntry {
    pub fn new(obj: PyObject) -> Self {
        SupervisorEntry {
            payload: RwLock::new(SafePyRef(obj)),
            version: AtomicU64::new(0),
        }
    }
}

/// SupervisorCore - The central state manager using references
#[pyclass(module = "theus_core")]
pub struct SupervisorCore {
    heap: Arc<RwLock<HashMap<String, Arc<SupervisorEntry>>>>,
}

#[pymethods]
impl SupervisorCore {
    #[new]
    pub fn new() -> Self {
        SupervisorCore {
            heap: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Read a value by key - returns reference (zero-copy)
    pub fn read(&self, py: Python, key: String) -> PyResult<Option<PyObject>> {
        let map_guard = self.heap.read().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
        })?;

        if let Some(entry_arc) = map_guard.get(&key) {
            let entry_guard = entry_arc.payload.read().map_err(|_| {
                pyo3::exceptions::PyRuntimeError::new_err("Entry Lock Poisoned")
            })?;
            Ok(Some(entry_guard.0.clone_ref(py)))
        } else {
            Ok(None)
        }
    }

    /// Write a value by key (creates if not exists)
    pub fn write(&self, _py: Python, key: String, val: PyObject) -> PyResult<()> {
        // Fast path: try update existing
        {
            let map_read = self.heap.read().map_err(|_| {
                pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
            })?;
            
            if let Some(entry_arc) = map_read.get(&key) {
                let mut entry_guard = entry_arc.payload.write().map_err(|_| {
                    pyo3::exceptions::PyRuntimeError::new_err("Entry Lock Poisoned")
                })?;
                entry_guard.0 = val;
                entry_arc.version.fetch_add(1, Ordering::SeqCst);
                return Ok(());
            }
        }

        // Slow path: insert new
        let mut map_write = self.heap.write().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
        })?;
        
        let entry = Arc::new(SupervisorEntry::new(val));
        map_write.insert(key, entry);
        Ok(())
    }

    /// Get version for a key
    pub fn get_version(&self, key: String) -> PyResult<Option<u64>> {
        let map_read = self.heap.read().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
        })?;
        
        if let Some(entry_arc) = map_read.get(&key) {
            Ok(Some(entry_arc.version.load(Ordering::SeqCst)))
        } else {
            Ok(None)
        }
    }

    /// Check if key exists
    pub fn contains(&self, key: String) -> PyResult<bool> {
        let map_read = self.heap.read().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
        })?;
        Ok(map_read.contains_key(&key))
    }

    /// Get all keys
    pub fn keys(&self) -> PyResult<Vec<String>> {
        let map_read = self.heap.read().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
        })?;
        Ok(map_read.keys().cloned().collect())
    }

    /// Remove a key
    pub fn remove(&self, key: String) -> PyResult<bool> {
        let mut map_write = self.heap.write().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Lock Poisoned")
        })?;
        Ok(map_write.remove(&key).is_some())
    }
}

impl Default for SupervisorCore {
    fn default() -> Self {
        Self::new()
    }
}

pub fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SupervisorCore>()?;
    Ok(())
}
