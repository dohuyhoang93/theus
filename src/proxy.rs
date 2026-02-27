use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple, PyAny, PyModule};
use crate::zones::{CAP_APPEND, CAP_UPDATE, CAP_DELETE};

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
// [RFC-001 §10] Removed `subclass` to eliminate __dict__ allocation.
// No Python code subclasses SupervisorProxy — verified by grep.
// Without `subclass`, PyO3 does not create per-instance __dict__,
// closing the __dict__ bypass attack surface at the C level.
#[pyclass(module = "theus_core")]
pub struct SupervisorProxy {
    /// The wrapped Python object
    // [INC-019] Renamed to 'inner' to ensure NO binding to '_target'
    pub(crate) inner: Py<PyAny>,
    /// Path for logging/permission: "domain.counter"
    path: String,
    /// If true, block all writes (for PURE processes)
    read_only: bool,
    /// Optional transaction for delta logging
    transaction: Option<Py<PyAny>>,
    /// [INC-013] If true, this proxy wraps a Shadow Object.
    /// Children of a Shadow are implicitly Shadows and should NOT trigger CoW.
    is_shadow: bool,
    /// [RFC-001] Capability Bitmask
    // [RFC-001] Expose capabilities to Python so AdminTransaction can elevate
    #[pyo3(get, set)]
    pub capabilities: u8,
}

#[pymethods]
impl SupervisorProxy {
    #[new]
    #[pyo3(signature = (target, path="".to_string(), read_only=false, transaction=None, is_shadow=false, capabilities=15))]
    pub fn new(
        target: PyObject,
        path: String,
        read_only: bool,
        transaction: Option<PyObject>,
        is_shadow: bool,
        capabilities: u8,
    ) -> Self {
        SupervisorProxy {
            inner: target,
            path,
            read_only,
            transaction,
            is_shadow,
            capabilities,
        }
    }

    /// [RFC-001 §10] Intercept ALL attribute access at C level.
    /// __getattribute__ runs BEFORE getset_descriptors (including __dict__).
    /// Without this, PyO3's auto-generated __dict__ descriptor bypasses __getattr__.
    fn __getattribute__(slf: &Bound<'_, Self>, name: &str) -> PyResult<PyObject> {
        if name == "__dict__" {
            // NOTE: Return empty dict instead of PermissionError.
            // Blocking with PermissionError breaks deepcopy() and any internal Python 
            // mechanism that probes __dict__ (AdminTransaction, pickle, etc.).
            // Returning empty dict is safe because:
            // 1. No real data is exposed
            // 2. Any mutation on the empty dict doesn't propagate (severity = LOW, proven)
            // 3. PyObject_GenericGetAttr won't re-trigger __getattribute__ recursion
            let dict = pyo3::types::PyDict::new(slf.py());
            return Ok(dict.into_any().unbind());
        }
        // NOTE: Delegate to default tp_getattro for all other attributes.
        // This preserves normal attribute resolution (methods, properties, etc.)
        // and falls through to __getattr__ for dynamic lookups.
        let py = slf.py();
        let name_obj = pyo3::types::PyString::new(py, name);
        unsafe {
            let result = pyo3::ffi::PyObject_GenericGetAttr(
                slf.as_ptr(),
                name_obj.as_ptr(),
            );
            if result.is_null() {
                Err(pyo3::PyErr::fetch(py))
            } else {
                Ok(PyObject::from_owned_ptr(py, result))
            }
        }
    }

    /// Get attribute - Returns original object (or nested Proxy)
    /// v3.1: Supports Dict dot-access (d.key) fallback
    fn __getattr__(&self, py: Python, name: String) -> PyResult<PyObject> {
        // Skip internal attributes, but intercept __dict__ with PermissionError
        // [RFC-001 §10] Block __dict__ to prevent bypassing Zone Physics
        if name == "__dict__" {
            return Err(pyo3::exceptions::PyPermissionError::new_err(
                "Direct access to '__dict__' is forbidden. Use the Context API to read/write fields safely."
            ));
        }
        if name.starts_with('_') {
            return Err(pyo3::exceptions::PyAttributeError::new_err(
                format!("'SupervisorProxy' object has no attribute '{}'", name)
            ));
        }

        let nested_path = if self.path.is_empty() {
            name.clone()
        } else {
            format!("{}.{}", self.path, name)
        };

        // [RFC-001] Check field-specific Zone Physics (Read Access)
        let zone = crate::zones::resolve_zone(&nested_path);
        let override_caps = crate::zones::get_physics_override(&nested_path);
        let zone_physics = override_caps.unwrap_or_else(|| crate::zones::get_zone_physics(&zone));
        let mut access_caps = self.capabilities & zone_physics;
        
        if (self.capabilities & 16) != 0 && !crate::zones::is_absolute_ceiling(&zone) {
            access_caps = 31u8;
        }

        if (access_caps & crate::zones::CAP_READ) == 0 {
            // [RFC-001 Handbook §1.1] Return None silently for non-admin reading PRIVATE 
            return Ok(py.None());
        }

        // 1. Try generic getattr (methods, object fields)
        let val_result = self.inner.getattr(py, name.as_str());
        
        let val = match val_result {
            Ok(v) => v,
            Err(_e) => {
                if self.inner.bind(py).is_instance_of::<PyDict>() {
                    match self.inner.call_method1(py, "__getitem__", (name.clone(),)) {
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
                    let _ = _e;
                     return Err(pyo3::exceptions::PyAttributeError::new_err(
                        format!(
                            "'SupervisorProxy[{}]' object has no attribute '{}'. (Path: '{}')", 
                            self.inner.bind(py).get_type().name()?, name, self.path
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
        let is_list = val.bind(py).is_instance_of::<PyList>();
        let has_dict = val.bind(py).hasattr("__dict__")?;
        
        if is_dict || is_list || has_dict {
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

            // Recalculate capabilities for nested path
            let child_caps = if (self.capabilities & 16) != 0 {
                31u8 // Preserve Admin Bypass
            } else {
                let zone = crate::zones::resolve_zone(&nested_path);
                let override_caps = crate::zones::get_physics_override(&nested_path);
                let zone_physics = override_caps.unwrap_or_else(|| crate::zones::get_zone_physics(&zone));
                self.capabilities & zone_physics
            };

            // [RFC-001] Feature 6: Block Direct Context __dict__ Mutation (Attack Surface §10)
            let is_read_only = self.read_only || name == "__dict__";

            Ok(SupervisorProxy::new(
                val_shadow,
                nested_path,
                is_read_only,
                tx_clone,
                is_child_shadow,
                child_caps,
            ).into_py(py))
        } else {
            Ok(val)
        }
    }

    #[pyo3(signature = (caps))]
    fn _set_capabilities(&mut self, caps: u8) {
        self.capabilities = caps;
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

        // [RFC-001] Check field-specific Zone Physics
        let full_path = if self.path.is_empty() {
            name.clone()
        } else {
            format!("{}.{}", self.path, name)
        };
        
        let zone = crate::zones::resolve_zone(&full_path);
        let override_caps = crate::zones::get_physics_override(&full_path);
        let zone_physics = override_caps.unwrap_or_else(|| crate::zones::get_zone_physics(&zone));
        let mut mutation_caps = self.capabilities & zone_physics;
        
        // Admin exception flag is bit 4 (16).
        if (self.capabilities & 16) != 0 && !crate::zones::is_absolute_ceiling(&zone) {
            mutation_caps = 31u8;
        }

        if (mutation_caps & crate::zones::CAP_UPDATE) == 0 {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Permission Denied: UPDATE capability required for '{}'. (Current Lens: {:04b})", full_path, mutation_caps)
            ));
        }

        let is_dict = self.inner.bind(py).is_instance_of::<PyDict>();

        // Log mutation if transaction exists
        if let Some(ref tx) = self.transaction {
            let full_path = if self.path.is_empty() {
                name.clone()
            } else {
                format!("{}.{}", self.path, name)
            };
            
            // Get old value for delta logging (handling Dict vs Object)
            let old_val = if is_dict {
                 self.inner.call_method1(py, "get", (name.as_str(),)).ok()
            } else {
                 self.inner.getattr(py, name.as_str()).ok()
            };
            
            // Call transaction.log_delta(path, old, new)
            // Call transaction.log_delta(path, old, new)
            match tx.bind(py).getattr("log_delta") {
                Ok(tx_bound) => {
                     if let Err(e) = tx_bound.call1((full_path, old_val, value.clone_ref(py))) {
                         eprintln!("ERROR: log_delta failed!");
                         e.print(py);
                     }
                },
                Err(e) => {
                    eprintln!("ERROR: Transaction object missing log_delta!");
                    e.print(py);
                }
            }
        }

        // Actually set the attribute/item
        // [v3.1.3 SECURITY FIX] Block mutations if no transaction is present!
        // Every state change in Theus MUST be tied to a transaction for audit and rollback.
        if self.transaction.is_some() {
            if is_dict {
                 self.inner.call_method1(py, "__setitem__", (name, value))?;
            } else {
                 self.inner.setattr(py, name.as_str(), value)?;
            }
            Ok(())
        } else {
            Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Supervisor blocked mutation to '{}.{}': No active transaction found. State is Immutable outside processes.", self.path, name)
            ))
        }
    }

    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        let key_str = key.bind(py).str()?.to_string();
        let nested_path = if self.path.is_empty() {
            key_str.clone()
        } else {
            format!("{}[{}]", self.path, key_str)
        };

        // [RFC-001] Check field-specific Zone Physics (Read Access)
        let zone = crate::zones::resolve_zone(&nested_path);
        let zone_physics = crate::zones::get_zone_physics(&zone);
        let mut access_caps = self.capabilities & zone_physics;
        
        if (self.capabilities & 16) != 0 && !crate::zones::is_absolute_ceiling(&zone) {
            access_caps = 31u8;
        }

        if (access_caps & crate::zones::CAP_READ) == 0 {
             return Ok(py.None());
        }

        let val = self.inner.call_method1(py, "__getitem__", (key.clone_ref(py),))?;

        // Check if value is a container (Dict/List/Object)

        // NOTE: Lists MUST be wrapped to prevent in-place mutations (append, pop, etc.)
        let is_dict = val.bind(py).is_instance_of::<PyDict>();
        let is_list = val.bind(py).is_instance_of::<PyList>();
        let has_dict = val.bind(py).hasattr("__dict__")?;

        if is_dict || is_list || has_dict {
            let tx_clone = self.transaction.as_ref().map(|t| t.clone_ref(py));
            
            let mut is_child_shadow = self.is_shadow;

            let val_shadow = if let Some(ref tx) = self.transaction {
                let tx_bound = tx.bind(py);
                
                if self.is_shadow {
                    // [FIX] Parent is Shadow -> Child is mutable part of Shadow Tree. 
                    // Use it directly to ensure mutations propagate to parent.
                    val.clone_ref(py)
                } else {
                    // [v3.1.2] Differential Shadow Optimization
                    match tx_bound.call_method1("get_shadow", (val.clone_ref(py), Some(nested_path.clone()))) {
                        Ok(s) => {
                            is_child_shadow = true;
                            s.unbind()
                        },
                        Err(e) => return Err(e)
                    }
                }
            } else {
                val.clone_ref(py)
            };

            // Recalculate capabilities for nested path
            let child_caps = if (self.capabilities & 16) != 0 {
                31u8 // Preserve Admin Bypass
            } else {
                let zone = crate::zones::resolve_zone(&nested_path);
                let override_caps = crate::zones::get_physics_override(&nested_path);
                let zone_physics = override_caps.unwrap_or_else(|| crate::zones::get_zone_physics(&zone));
                self.capabilities & zone_physics
            };

            let proxy = SupervisorProxy::new(
                val_shadow,
                nested_path,
                self.read_only,
                tx_clone,
                is_child_shadow,
                child_caps,
            );
            Ok(Py::new(py, proxy)?.into_any())
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

        let key_str_tmp = key.bind(py).str()?.to_string();
        let full_path_tmp = if self.path.is_empty() {
            key_str_tmp.clone()
        } else {
            format!("{}[{}]", self.path, key_str_tmp)
        };

        // [RFC-001] Check field-specific Zone Physics
        let zone = crate::zones::resolve_zone(&full_path_tmp);
        let override_caps = crate::zones::get_physics_override(&full_path_tmp);
        let zone_physics = override_caps.unwrap_or_else(|| crate::zones::get_zone_physics(&zone));
        let mut mutation_caps = self.capabilities & zone_physics;
        
        if (self.capabilities & 16) != 0 && !crate::zones::is_absolute_ceiling(&zone) {
            mutation_caps = 31u8;
        }

        if (mutation_caps & CAP_UPDATE) == 0 {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Permission Denied: UPDATE capability required for item assignment at '{}'. (Current Lens: {:04b})", full_path_tmp, mutation_caps)
            ));
        }

        // [v3.1.3 SECURITY FIX] Block mutations if no transaction is present!
        if self.transaction.is_none() {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Supervisor blocked mutation to path '{}': No active transaction found.", self.path)
            ));
        }

        let tx = self.transaction.as_ref().unwrap();

        // Log if transaction exists
        let key_str = key.bind(py).str()?.to_string();
        let full_path = if self.path.is_empty() {
            key_str
        } else {
            format!("{}[{}]", self.path, key.bind(py).str()?)
        };
        
        let old_val = self.inner.call_method1(py, "get", (key.clone_ref(py),)).ok();
        
        if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
            let _ = tx_bound.call1((full_path, old_val, value.clone_ref(py)));
        }

        self.inner.call_method1(py, "__setitem__", (key, value))?;
        Ok(())
    }

    /// String representation - More descriptive for debugging
    fn __repr__(&self, py: Python) -> PyResult<String> {
        let type_name = self.inner.bind(py).get_type().name()?.to_string();
        // Don't print full target repr if it's huge, just type and path
        Ok(format!("<SupervisorProxy[{}] at path='{}' cap={:04b}>", type_name, self.path, self.capabilities))
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
        self.inner.call_method1(py, "__contains__", (key,))?.extract(py)
    }

    /// Iterator support
    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        self.inner.call_method0(py, "__iter__")
    }

    /// Conversion to dict (Delegates to target or returns None)
    fn to_dict(&self, py: Python) -> PyResult<PyObject> {
        let inner = self.inner.bind(py);
        if inner.hasattr("model_dump")? {
            inner.call_method0("model_dump").map(|x| x.unbind())
        } else if inner.hasattr("dict")? {
            inner.call_method0("dict").map(|x| x.unbind())
        } else if inner.hasattr("to_dict")? {
            inner.call_method0("to_dict").map(|x| x.unbind())
        } else if inner.is_instance_of::<PyDict>() {
            // It is already a dict, but target is PyAny. Return clone as dict.
            // Actually, usually we want a copy.
            inner.call_method0("copy").map(|x| x.unbind())
        } else {
             Err(pyo3::exceptions::PyAttributeError::new_err("Wrapped object has no to_dict/model_dump"))
        }
    }

    // === List Methods (Guarded) ===

    fn append(&self, py: Python, item: PyObject) -> PyResult<()> {
        if self.capabilities & CAP_APPEND == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: APPEND capability required for .append() at '{}'", self.path)));
        }
        self.inner.call_method1(py, "append", (item,))?;
        
        // Log Delta (Explicit SET for engine compatibility)
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
            }
        }
        Ok(())
    }

    fn extend(&self, py: Python, iterable: PyObject) -> PyResult<()> {
        if self.capabilities & CAP_APPEND == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: APPEND capability required for .extend() at '{}'", self.path)));
        }
        self.inner.call_method1(py, "extend", (iterable,))?;
        
        // Log Delta
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
            }
        }
        Ok(())
    }

    fn insert(&self, py: Python, index: PyObject, item: PyObject) -> PyResult<()> {
        if self.capabilities & CAP_APPEND == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: APPEND capability required for .insert() at '{}'", self.path)));
        }
        self.inner.call_method1(py, "insert", (index, item))?;
        
        // Log Delta
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
            }
        }
        Ok(())
    }

    fn remove(&self, py: Python, value: PyObject) -> PyResult<()> {
        if self.capabilities & CAP_DELETE == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: DELETE capability required for .remove() at '{}'", self.path)));
        }
        self.inner.call_method1(py, "remove", (value,))?;
        
        // Log Delta
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
            }
        }
        Ok(())
    }

    fn sort(&self, py: Python, kwargs: Option<&Bound<PyDict>>) -> PyResult<()> {
        if self.capabilities & CAP_UPDATE == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: UPDATE capability required for .sort() at '{}'", self.path)));
        }
        self.inner.call_method(py, "sort", (), kwargs)?;
        
        // Log Delta
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
            }
        }
        Ok(())
    }

    fn reverse(&self, py: Python) -> PyResult<()> {
        if self.capabilities & CAP_UPDATE == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: UPDATE capability required for .reverse() at '{}'", self.path)));
        }
        self.inner.call_method0(py, "reverse")?;
        
        // Log Delta
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
            }
        }
        Ok(())
    }

    fn clear(&self, py: Python) -> PyResult<()> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        if (self.capabilities & CAP_DELETE) == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(format!("Permission Denied: DELETE capability required for .clear() at '{}'", self.path)));
        }

        let is_list = self.inner.bind(py).is_instance_of::<PyList>();
        
        // Execute clear
        self.inner.call_method0(py, "clear")?;

        // Log Delta
        if let Some(ref tx) = self.transaction {
            if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                if is_list {
                    // For lists, log whole empty list
                    let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
                } else {
                    // For dicts, we could log all keys being removed, or just use the Shadow Inference in commit.
                    // But to be safe and explicit:
                    let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
                }
            }
        }
        Ok(())
    }

    // === Getters for introspection ===
    
    /// Expose internals as dict for Pydantic/Standard Library compatibility
    #[getter]
    fn __dict__(&self, py: Python) -> PyResult<PyObject> {
        self.to_dict(py)
    }

    // === Mapping Protocol Implementation ===

    fn __len__(&self, py: Python) -> PyResult<usize> {
        self.inner.call_method0(py, "__len__")?.extract(py)
    }

    fn __richcmp__(&self, py: Python, other: PyObject, op: pyo3::basic::CompareOp) -> PyResult<PyObject> {
        match op {
            pyo3::basic::CompareOp::Eq => {
                // If other is dict, compare target with dict
                self.inner.call_method1(py, "__eq__", (other,))
            },
            pyo3::basic::CompareOp::Ne => {
                self.inner.call_method1(py, "__ne__", (other,))
            },
            _ => Ok(py.NotImplemented()),
        }
    }

    fn get(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        // Safe get that wraps result
        let val_res = self.inner.call_method1(py, "get", (key.clone_ref(py), default));
        match val_res {
            Ok(val) => self._wrap_result(py, key.bind(py).str()?.to_string(), val),
            Err(e) => Err(e),
        }
    }

    fn keys(&self, py: Python) -> PyResult<PyObject> {
        self.inner.call_method0(py, "keys")
    }

    fn values(&self, py: Python) -> PyResult<PyObject> {
        let values_view = self.inner.call_method0(py, "values")?;
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
        let items_view = self.inner.call_method0(py, "items")?;
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
        
        // [RFC-001] Check UPDATE Capability
        if (self.capabilities & CAP_UPDATE) == 0 {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Permission Denied: UPDATE capability required for .update() at '{}'. (Current Lens: {:04b})", self.path, self.capabilities)
            ));
        }

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
                 let old_val = self.inner.call_method1(py, "get", (k.to_object(py),)).ok(); // Raw get is fine for log
                 
                 // Log delta
                 if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                    let _ = tx_bound.call1((full_path, old_val, v));
                 }
             }
        }
        
        // 3. Apply updates to target
        self.inner.call_method(py, "update", (updates,), None)?;
        Ok(())
    }

    #[pyo3(signature = (key_or_index=None, default=None))]
    fn pop(&self, py: Python, key_or_index: Option<PyObject>, default: Option<PyObject>) -> PyResult<PyObject> {
        if self.read_only {
            return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        if (self.capabilities & CAP_DELETE) == 0 {
            return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Permission Denied: DELETE capability required for .pop() at '{}'. (Current Lens: {:04b})", self.path, self.capabilities)
            ));
        }

        let is_list = self.inner.bind(py).is_instance_of::<PyList>();

        // Log mutation
        if let Some(ref tx) = self.transaction {
            if is_list {
                // For lists, log the whole list path since indices shift
                if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                    let _ = tx_bound.call1((self.path.clone(), py.None(), self.inner.clone_ref(py)));
                }
            } else if let Some(ref koi) = key_or_index {
                // For dicts, log specific key
                let key_str = koi.bind(py).str()?.to_string();
                let full_path = if self.path.is_empty() {
                    key_str.clone()
                } else {
                    format!("{}.{}", self.path, key_str)
                };
                
                if self.inner.call_method1(py, "__contains__", (koi.clone_ref(py),))?.extract(py)? {
                     let old_val = self.inner.call_method1(py, "get", (koi.clone_ref(py),)).ok();
                     if let Ok(tx_bound) = tx.bind(py).getattr("log_delta") {
                        let _ = tx_bound.call1((full_path, old_val, py.None()));
                     }
                }
            }
        }

        // Execute pop
        if is_list {
             // List.pop takes index, not (key, default)
             let koi = key_or_index.unwrap_or_else(|| (-1i32).to_object(py));
             self.inner.call_method1(py, "pop", (koi,))
        } else {
             let koi = key_or_index.ok_or_else(|| pyo3::exceptions::PyTypeError::new_err("pop() expected at least 1 argument, got 0"))?;
             self.inner.call_method1(py, "pop", (koi, default))
        }
    }

    fn popitem(&self, py: Python) -> PyResult<PyObject> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        if (self.capabilities & CAP_DELETE) == 0 {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Permission Denied: DELETE capability required for .popitem() at '{}'. (Current Lens: {:04b})", self.path, self.capabilities)
            ));
        }

        // Hard to log beforehand without knowing what will be popped.
        // Strategy: Peek or Pop then Log?
        // Pop then Log is safer for consistency.
        
        let res = self.inner.call_method0(py, "popitem")?;
        
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


    fn setdefault(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        if self.read_only {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("PURE process cannot write to '{}'", self.path)
            ));
        }

        if (self.capabilities & CAP_UPDATE) == 0 {
             return Err(pyo3::exceptions::PyPermissionError::new_err(
                format!("Permission Denied: UPDATE capability required for .setdefault() at '{}'. (Current Lens: {:04b})", self.path, self.capabilities)
            ));
        }
        
        // Logic: if key exists, return it (wrapped). If not, set it (log) and return it (wrapped).
        let contains = self.inner.call_method1(py, "__contains__", (key.clone_ref(py),))?.extract::<bool>(py)?;
        
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

        let res = self.inner.call_method1(py, "setdefault", (key.clone_ref(py), default))?;
        
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
                self.capabilities, // Inherit
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
        self.inner.clone_ref(py)
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
            self.inner.clone_ref(py),
            self.path.clone().into_py(py),
            self.read_only.into_py(py),
            self.is_shadow.into_py(py),
            self.capabilities.into_py(py)
        ]);
        Ok(tuple.into())
    }

    fn __setstate__(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let tuple = state.downcast_bound::<PyTuple>(py)?;
        self.inner = tuple.get_item(0)?.unbind();
        self.path = tuple.get_item(1)?.extract()?;
        self.read_only = tuple.get_item(2)?.extract()?;
        // Handle backwards compat for old pickles (len=3)
        if tuple.len() >= 4 {
             self.is_shadow = tuple.get_item(3)?.extract()?;
        } else {
             self.is_shadow = false;
        }
        if tuple.len() >= 5 {
             self.capabilities = tuple.get_item(4)?.extract()?;
        } else {
             self.capabilities = 15; // Default ALL
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
             false.into_py(py),
             15u8.into_py(py)
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
