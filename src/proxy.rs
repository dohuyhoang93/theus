// Import at top of file
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple, PyAny, PyModule};

// use crate::engine::Transaction;


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
    /// [INC-013] If true, this proxy wraps a Shadow Object.
    /// Children of a Shadow are implicitly Shadows and should NOT trigger CoW.
    is_shadow: bool,
}

#[pymethods]
impl SupervisorProxy {
    #[new]
    #[pyo3(signature = (target, path="".to_string(), read_only=false, transaction=None, is_shadow=false))]
    pub fn new(
        target: Py<PyAny>,
        path: String,
        read_only: bool,
        transaction: Option<Py<PyAny>>,
        is_shadow: bool,
    ) -> Self {
        SupervisorProxy {
            target,
            path,
            read_only,
            transaction,
            is_shadow,
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
            
            // [INC-013] Double Shadowing Logic
            let mut is_child_shadow = self.is_shadow;

            // v3.1 CoW: Get Shadow (No Stitching)
            let val_shadow = if let Some(ref tx) = self.transaction {
                let tx_bound = tx.bind(py);
                
                if self.is_shadow {
                    // Parent is Shadow -> Child is mutable part of Shadow Tree. Skip CoW.
                    val.clone_ref(py)
                } else {
                    match tx_bound.call_method1("get_shadow", (val.clone_ref(py), Some(nested_path.clone()))) {
                        Ok(s) => {
                            is_child_shadow = true; // Result of get_shadow is always tracked
                            s.unbind()
                        },
                        Err(_) => val
                    }
                }
            } else {
                val
            };

            Ok(SupervisorProxy::new(
                val_shadow,
                nested_path,
                self.read_only,
                tx_clone,
                is_child_shadow,
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
            
            // [INC-013] Double Shadowing Logic
            let mut is_child_shadow = self.is_shadow;

            // v3.1 CoW: Get Shadow (No Stitching)
            let val_shadow = if let Some(ref tx) = self.transaction {
                let tx_bound = tx.bind(py);
                
                if self.is_shadow {
                    val.clone_ref(py)
                } else {
                    match tx_bound.call_method1("get_shadow", (val.clone_ref(py), Some(nested_path.clone()))) {
                        Ok(s) => {
                            is_child_shadow = true;
                            s.unbind()
                        },
                        Err(_) => val
                    }
                }
            } else {
                val
            };

            Ok(SupervisorProxy::new(
                val_shadow,
                nested_path,
                self.read_only,
                tx_clone,
                is_child_shadow,
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
    
    /// Expose internals as dict for Pydantic/Standard Library compatibility
    #[getter]
    fn __dict__(&self, py: Python) -> PyResult<PyObject> {
        self.to_dict(py)
    }

    // === Mapping Protocol Implementation ===

    fn __len__(&self, py: Python) -> PyResult<usize> {
        self.target.call_method0(py, "__len__")?.extract(py)
    }

    fn __richcmp__(&self, py: Python, other: PyObject, op: pyo3::basic::CompareOp) -> PyResult<PyObject> {
        match op {
            pyo3::basic::CompareOp::Eq => {
                // If other is dict, compare target with dict
                self.target.call_method1(py, "__eq__", (other,))
            },
            pyo3::basic::CompareOp::Ne => {
                self.target.call_method1(py, "__ne__", (other,))
            },
            _ => Ok(py.NotImplemented()),
        }
    }

    fn get(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        // Safe get that wraps result
        let val_res = self.target.call_method1(py, "get", (key.clone_ref(py), default));
        match val_res {
            Ok(val) => self._wrap_result(py, key.bind(py).str()?.to_string(), val),
            Err(e) => Err(e),
        }
    }

    fn keys(&self, py: Python) -> PyResult<PyObject> {
        self.target.call_method0(py, "keys")
    }

    fn values(&self, py: Python) -> PyResult<PyObject> {
        let values_view = self.target.call_method0(py, "values")?;
        // Robustness: Convert view to list via builtins to handle any iterable safely
        let builtins = py.import_bound("builtins")?;
        let values_list = builtins.call_method1("list", (values_view,))?;
        let values_py_list = values_list.downcast::<PyList>()?;
        
        let mut wrapped_list = Vec::new();
        for item in values_py_list.iter() {
             let wrapped = self._wrap_result(py, "?".to_string(), item.unbind())?;
             wrapped_list.push(wrapped);
        }
        Ok(PyList::new_bound(py, wrapped_list).into())
    }

    fn items(&self, py: Python) -> PyResult<PyObject> {
        let items_view = self.target.call_method0(py, "items")?;
        // Robustness: Convert view to list via builtins
        let builtins = py.import_bound("builtins")?;
        let items_list = builtins.call_method1("list", (items_view,))?;
        let items_py_list = items_list.downcast::<PyList>()?;

        let mut wrapped_items = Vec::new();
        
        for item in items_py_list.iter() {
            // item is tuple (k, v)
            if let Ok(tuple) = item.downcast::<PyTuple>() {
                 if tuple.len() == 2 {
                     let k = tuple.get_item(0)?;
                     let v = tuple.get_item(1)?;
                     let k_str = k.str()?.to_string();
                     let wrapped_v = self._wrap_result(py, k_str, v.unbind())?;
                     
                     // Safe Tuple Creation
                     let elements = vec![k.unbind(), wrapped_v];
                     let new_tuple = PyTuple::new_bound(py, elements);
                     wrapped_items.push(new_tuple.unbind());
                 }
            }
        }
        Ok(PyList::new_bound(py, wrapped_items).into())
    }

    // === Zero Trust Mutators ===

    fn update(&self, py: Python, other: Option<PyObject>, kwargs: Option<PyObject>) -> PyResult<()> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        // We need to construct the full dict of updates to log them properly
        // This is expensive but necessary for Zero Trust Audit
        // 1. Create a temporary dict with the updates
        let builtins = py.import_bound("builtins")?;
        let dict_cls = builtins.getattr("dict")?;
        
        let header = PyTuple::new_bound(py, other.iter().map(|o| o.clone_ref(py)));
        
        let kwargs_dict = if let Some(k) = kwargs {
             Some(k.downcast_bound::<PyDict>(py)?.clone())
        } else {
             None
        };

        let updates = dict_cls.call(header, kwargs_dict.as_ref())?;
        let updates_dict = updates.downcast::<PyDict>()?;

        // 2. Iterate and log each change
        if let Some(ref tx) = self.transaction {
             for (k, v) in updates_dict.iter() {
                 let key_str = k.str()?.to_string();
                 let full_path = if self.path.is_empty() {
                    key_str.clone()
                 } else {
                    format!("{}.{}", self.path, key_str)
                 };

                 // Get old value
                 // Get old value
                 let old_val = self.target.call_method1(py, "get", (k.to_object(py),)).ok(); // Raw get is fine for log
                 
                 // Log delta
                 if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                    let _ = tx_bound.call1((full_path, old_val, v));
                 }
             }
        }
        
        // 3. Apply updates to target
        self.target.call_method(py, "update", (updates,), None)?;
        Ok(())
    }

    fn pop(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        let key_str = key.bind(py).str()?.to_string();
        let full_path = if self.path.is_empty() {
            key_str.clone()
        } else {
            format!("{}.{}", self.path, key_str)
        };

        // Log if key exists
        if let Some(ref tx) = self.transaction {
            if self.target.call_method1(py, "__contains__", (key.clone_ref(py),))?.extract(py)? {
                 let old_val = self.target.call_method1(py, "get", (key.clone_ref(py),)).ok();
                 if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                    let _ = tx_bound.call1((full_path, old_val, py.None())); // New is None (deleted)
                 }
            }
        }

        // Execute pop
        self.target.call_method1(py, "pop", (key, default))
    }

    fn popitem(&self, py: Python) -> PyResult<PyObject> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        // Hard to log beforehand without knowing what will be popped.
        // Strategy: Peek or Pop then Log?
        // Pop then Log is safer for consistency.
        
        let res = self.target.call_method0(py, "popitem")?;
        
        // It returns (key, value)
        if let Some(ref tx) = self.transaction {
             if let Ok(tuple) = res.bind(py).downcast::<PyTuple>() {
                 if tuple.len() == 2 {
                    let k = tuple.get_item(0)?;
                    let v = tuple.get_item(1)?;
                    
                    let key_str = k.str()?.to_string();
                    let full_path = if self.path.is_empty() {
                        key_str
                    } else {
                        format!("{}.{}", self.path, key_str)
                    };

                    if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                        // Log deletion: old=v, new=None
                        let _ = tx_bound.call1((full_path, v, py.None())); 
                    }
                 }
             }
        }
        
        Ok(res)
    }

    fn clear(&self, py: Python) -> PyResult<()> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        if let Some(ref tx) = self.transaction {
            // Expensive log: Must log deletion of ALL keys?
            // Or just log "cleared"?
            // The current log_delta is path-based. 
            // Correct Audit: Iterate all keys and log delete for each?
            
            // For performance, maybe we iterate keys currently.
            let keys_view = self.target.call_method0(py, "keys")?;
            // We can iterate without list conversion if we are careful, but list is safer before modification
            let builtins = py.import_bound("builtins")?;
            let keys_list = builtins.call_method1("list", (keys_view,))?;
            let keys_py_list = keys_list.downcast::<PyList>()?;

            for k in keys_py_list.iter() {
                 let key_str = k.str()?.to_string();
                 let full_path = if self.path.is_empty() {
                    key_str.clone()
                 } else {
                    format!("{}.{}", self.path, key_str)
                 };
                 
                 let old_val = self.target.call_method1(py, "get", (k.to_object(py),)).ok();
                 
                 if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                    let _ = tx_bound.call1((full_path, old_val, py.None()));
                 }
            }
        }

        self.target.call_method0(py, "clear")?;
        Ok(())
    }

    fn setdefault(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }
        
        // Logic: if key exists, return it (wrapped). If not, set it (log) and return it (wrapped).
        let contains = self.target.call_method1(py, "__contains__", (key.clone_ref(py),))?.extract::<bool>(py)?;
        
        if !contains {
            // Will set. Log it.
             if let Some(ref tx) = self.transaction {
                let key_str = key.bind(py).str()?.to_string();
                let full_path = if self.path.is_empty() {
                    key_str.clone()
                } else {
                    format!("{}.{}", self.path, key_str)
                };
                
                let default_val = default.as_ref().map(|o| o.clone_ref(py)).unwrap_or(py.None());
                
                if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                    let _ = tx_bound.call1((full_path, py.None(), default_val));
                }
             }
        }

        let res = self.target.call_method1(py, "setdefault", (key.clone_ref(py), default))?;
        
        // Wrap result
        let key_str = key.bind(py).str()?.to_string();
        self._wrap_result(py, key_str, res)
    }
    fn _wrap_result(&self, py: Python, key_or_path: String, val: PyObject) -> PyResult<PyObject> {
         let nested_path = if self.path.is_empty() {
            key_or_path
        } else {
            format!("{}.{}", self.path, key_or_path) 
        };

        let val_bound = val.bind(py);
        let is_dict = val_bound.is_instance_of::<PyDict>();
        let has_dict = val_bound.hasattr("__dict__")?;
        let is_list = val_bound.is_instance_of::<PyList>();

        // 1. Handle Dicts and Objects (Existing Logic)
        if is_dict || has_dict {
            let tx_clone = self.transaction.as_ref().map(|t| t.clone_ref(py));
            
            // [INC-013] Double Shadowing Logic
            let mut is_child_shadow = self.is_shadow;

            // CoW: Get Shadow
            let val_shadow = if let Some(ref tx) = self.transaction {
                let tx_bound = tx.bind(py);
                
                if self.is_shadow {
                    val.clone_ref(py)
                } else {
                    match tx_bound.call_method1("get_shadow", (val.clone_ref(py), Some(nested_path.clone()))) {
                        Ok(s) => {
                            is_child_shadow = true;
                            s.unbind()
                        },
                        Err(_) => val
                    }
                }
            } else {
                val
            };

            return Ok(SupervisorProxy::new(
                val_shadow,
                nested_path,
                self.read_only,
                tx_clone,
                is_child_shadow,
            ).into_py(py));
        }
        
        // 2. [NEW] Handle Lists (Passive Inference Registration)
        if is_list {
             if let Some(ref tx) = self.transaction {
                 // Get Shadow for List to ensure it is registered in full_path_map
                 let tx_bound = tx.bind(py);
                 let val_shadow = match tx_bound.call_method1("get_shadow", (val.clone_ref(py), Some(nested_path.clone()))) {
                     Ok(s) => s.unbind(),
                     Err(_) => val.clone_ref(py)
                 };
                 // Return Raw Shadow List (no Proxy wrapper)
                 return Ok(val_shadow.into_py(py));
             }
        }

        Ok(val)
    }
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

    // === Pickle Support (v3.2) ===
    
    fn __getstate__(&self, py: Python) -> PyResult<PyObject> {
        // We pickle the target and metadata.
        // We LOSE transaction context across pickle boundaries usually (e.g. multiprocessing)
        // unless we reconstruct it. But transaction is ephemeral.
        // So we pickle as detached (read_only=true usually for workers?)
        // Or if we need to write back, we need to re-attach context manually.
        // For now: Safe default is pickle as Read-Only data container.
        let tuple = PyTuple::new_bound(py, vec![
            self.target.clone_ref(py),
            self.path.clone().into_py(py),
            self.read_only.into_py(py),
            self.is_shadow.into_py(py)
        ]);
        Ok(tuple.into())
    }

    fn __setstate__(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let tuple = state.downcast_bound::<PyTuple>(py)?;
        self.target = tuple.get_item(0)?.unbind();
        self.path = tuple.get_item(1)?.extract()?;
        self.read_only = tuple.get_item(2)?.extract()?;
        // Handle backwards compat for old pickles (len=3)
        if tuple.len() >= 4 {
             self.is_shadow = tuple.get_item(3)?.extract()?;
        } else {
             self.is_shadow = false;
        }
        self.transaction = None; // Detached from transaction after unpickle
        Ok(())
    }

    fn __getnewargs__(&self, py: Python) -> PyResult<PyObject> {
        // Provide dummy args to satisfy __new__ signature during unpickling
        // (target, path, read_only, transaction)
        let tuple = PyTuple::new_bound(py, vec![
             py.None(),
             "".into_py(py),
             true.into_py(py),
             py.None(),
             false.into_py(py)
        ]);
        Ok(tuple.into())
    }
}

// =============================================================================
// Module Registration
// =============================================================================

pub fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SupervisorProxy>()?;
    Ok(())
}
