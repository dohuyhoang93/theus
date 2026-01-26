use pyo3::prelude::*;
use pyo3::types::PyDict;

// =============================================================================
// SupervisorProxy - Wraps Python object references for mutation tracking
// =============================================================================
// 
// Purpose: Replace FrozenDict with a Proxy that:
// 1. Returns the SAME Python object (preserves idiomatics)
// 2. Intercepts writes for logging/permission checking
// 3. Works with existing Transaction rollback mechanism
// =============================================================================

// SafePyRef Removed (Unused)

/// SupervisorProxy - The Gatekeeper for Python object access
/// 
/// Unlike FrozenDict which returns copies, SupervisorProxy returns
/// the original Python object while intercepting mutations.
#[pyclass(module = "theus_core", subclass)]
pub struct SupervisorProxy {
    /// The wrapped Python object
    target: Py<PyAny>,
    /// Path for logging/permission: "domain.counter"
    path: String,
    /// If true, block all writes (for PURE processes)
    read_only: bool,
    /// Optional transaction for delta logging
    transaction: Option<Py<PyAny>>,
}

#[pymethods]
impl SupervisorProxy {
    #[new]
    #[pyo3(signature = (target, path="".to_string(), read_only=false, transaction=None))]
    pub fn new(
        target: Py<PyAny>,
        path: String,
        read_only: bool,
        transaction: Option<Py<PyAny>>,
    ) -> Self {
        SupervisorProxy {
            target,
            path,
            read_only,
            transaction,
        }
    }

    /// Get attribute - Returns original object (or nested Proxy)
    /// v3.1: Supports Dict dot-access (d.key) fallback
    fn __getattr__(&self, py: Python, name: String) -> PyResult<PyObject> {
        // Skip internal attributes
        if name.starts_with('_') {
            return Err(pyo3::exceptions::PyAttributeError::new_err(
                format!("'SupervisorProxy' object has no attribute '{}'", name)
            ));
        }

        // 1. Try generic getattr (methods, object fields)
        let val_result = self.target.getattr(py, name.as_str());
        
        let val = match val_result {
            Ok(v) => v,
            Err(_e) => {
                if self.target.bind(py).is_instance_of::<PyDict>() {
                    match self.target.call_method1(py, "__getitem__", (name.clone(),)) {
                        Ok(v) => v,
                        Err(_) => {
                            // If key missing, return original error but enriched
                            return Err(pyo3::exceptions::PyAttributeError::new_err(
                                format!(
                                    "'SupervisorProxy[dict]' object has no attribute '{}'. (Hint: Key '{}' missing in wrapped dict at path '{}')", 
                                    name, name, self.path
                                )
                            ));
                        }, 
                    }
                } else {
                    // Enrich standard attribute error (e.g. object has no attribute)
                    // We can just return _e, but enriched is nicer.
                    // However, to keep it simple and avoid clippy complexity with unused _e:
                    // If we use _e, we satisfy the compiler.
                    // But if we want enriched, we ignore _e.
                    let _ = _e;
                     return Err(pyo3::exceptions::PyAttributeError::new_err(
                        format!(
                            "'SupervisorProxy[{}]' object has no attribute '{}'. (Path: '{}')", 
                            self.target.bind(py).get_type().name()?, name, self.path
                        )
                    ));
                }
            }
        };

        // Build nested path
        let nested_path = if self.path.is_empty() {
            name.clone()
        } else {
            format!("{}.{}", self.path, name)
        };

        // Wrap nested dicts/objects in Proxy for continued tracking
        let is_dict = val.bind(py).is_instance_of::<PyDict>();
        let has_dict = val.bind(py).hasattr("__dict__")?;
        
        // DEBUG PRINT
        // println!("DEBUG: Proxy path='{}' getattr='{}' -> val_type='{}' is_dict={} has_dict={}", 
        //    self.path, name, val.bind(py).get_type().name()?, is_dict, has_dict);

        if is_dict || has_dict {
            let tx_clone = self.transaction.as_ref().map(|t| t.clone_ref(py));
            Ok(SupervisorProxy::new(
                val,
                nested_path,
                self.read_only,
                tx_clone,
            ).into_py(py))
        } else {
            Ok(val)
        }
    }

    /// Set attribute - Intercept for logging and permission check
    /// v3.1: Supports Dict dot-access (d.key = val -> d['key'] = val)
    fn __setattr__(&self, py: Python, name: String, value: PyObject) -> PyResult<()> {
        // Block writes on read-only proxy (PURE processes)
        if self.read_only {
            return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}.{}'", self.path, name)
            ));
        }

        let is_dict = self.target.bind(py).is_instance_of::<PyDict>();

        // Log mutation if transaction exists
        if let Some(ref tx) = self.transaction {
            let full_path = if self.path.is_empty() {
                name.clone()
            } else {
                format!("{}.{}", self.path, name)
            };
            
            // Get old value for delta logging (handling Dict vs Object)
            let old_val = if is_dict {
                 self.target.call_method1(py, "get", (name.as_str(),)).ok()
            } else {
                 self.target.getattr(py, name.as_str()).ok()
            };
            
            // Call transaction.log_delta(path, old, new)
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((full_path, old_val, value.clone_ref(py)));
            }
        }

        // Actually set the attribute/item
        if is_dict {
             self.target.call_method1(py, "__setitem__", (name, value))?;
        } else {
             self.target.setattr(py, name.as_str(), value)?;
        }
        Ok(())
    }

    /// Get item - For dict-like access ctx.domain["key"]
    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        let val = self.target.call_method1(py, "__getitem__", (key.clone_ref(py),))?;
        
        // Build nested path
        let key_str = key.bind(py).str()?.to_string();
        let nested_path = if self.path.is_empty() {
            key_str
        } else {
            format!("{}[{}]", self.path, key_str)
        };

        // Wrap if needed
        if val.bind(py).is_instance_of::<PyDict>() || val.bind(py).hasattr("__dict__")? {
            let tx_clone = self.transaction.as_ref().map(|t| t.clone_ref(py));
            Ok(SupervisorProxy::new(
                val,
                nested_path,
                self.read_only,
                tx_clone,
            ).into_py(py))
        } else {
            Ok(val)
        }
    }

    /// Set item - For dict-like access ctx.domain["key"] = value
    fn __setitem__(&self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
        if self.read_only {
            return Err(pyo3::exceptions::PyPermissionError::new_err(
                "PURE process cannot write"
            ));
        }

        // Log if transaction exists
        if let Some(ref tx) = self.transaction {
            let key_str = key.bind(py).str()?.to_string();
            let full_path = if self.path.is_empty() {
                key_str
            } else {
                format!("{}[{}]", self.path, key.bind(py).str()?)
            };
            
            let old_val = self.target.call_method1(py, "get", (key.clone_ref(py),)).ok();
            
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((full_path, old_val, value.clone_ref(py)));
            }
        }

        self.target.call_method1(py, "__setitem__", (key, value))?;
        Ok(())
    }

    /// String representation - More descriptive for debugging
    fn __repr__(&self, py: Python) -> PyResult<String> {
        let type_name = self.target.bind(py).get_type().name()?.to_string();
        // Don't print full target repr if it's huge, just type and path
        Ok(format!("<SupervisorProxy[{}] at path='{}'>", type_name, self.path))
    }

    fn __str__(&self, py: Python) -> PyResult<String> {
        self.__repr__(py)
    }

    /// Helper for users confused by type checks
    /// "isinstance(proxy, dict)" fails, so we provide this hint.
    fn is_proxy(&self) -> bool {
        true
    }

    /// Check if key exists (for 'in' operator)
    fn __contains__(&self, py: Python, key: PyObject) -> PyResult<bool> {
        self.target.call_method1(py, "__contains__", (key,))?.extract(py)
    }

    /// Iterator support
    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        self.target.call_method0(py, "__iter__")
    }

    /// Conversion to dict (Delegates to target or returns None)
    fn to_dict(&self, py: Python) -> PyResult<PyObject> {
        if self.target.bind(py).hasattr("to_dict")? {
            self.target.call_method0(py, "to_dict")
        } else if self.target.bind(py).is_instance_of::<PyDict>() {
            // It is already a dict, but target is PyAny. Return clone as dict.
            // Actually, usually we want a copy.
            self.target.call_method0(py, "copy")
        } else {
             Err(pyo3::exceptions::PyAttributeError::new_err("Wrapped object has no to_dict"))
        }
    }

    // === Getters for introspection ===
    
    #[getter]
    fn path(&self) -> &str {
        &self.path
    }

    #[getter]
    fn read_only(&self) -> bool {
        self.read_only
    }

    /// Get the underlying target (for internal use)
    #[getter]
    fn supervisor_target(&self, py: Python) -> PyObject {
        self.target.clone_ref(py)
    }
}

// =============================================================================
// Module Registration
// =============================================================================

pub fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SupervisorProxy>()?;
    Ok(())
}
