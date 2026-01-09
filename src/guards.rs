use pyo3::prelude::*;
use pyo3::exceptions::PyPermissionError;
use pyo3::types::{PyList, PyDict};
use crate::delta::Transaction;
use crate::structures::{TrackedList, TrackedDict, FrozenList, FrozenDict};
use crate::zones::{resolve_zone, ContextZone};

#[pyclass]
pub struct ContextGuard {
    #[pyo3(get, name = "_target")]
    target: PyObject,
    allowed_inputs: Vec<String>,
    allowed_outputs: Vec<String>,
    path_prefix: String,
    tx: Option<Py<Transaction>>, 
    is_admin: bool,
    strict_mode: bool,
}

impl ContextGuard {
    pub fn new_internal(target: PyObject, inputs: Vec<String>, outputs: Vec<String>, tx: Option<Py<Transaction>>, is_admin: bool, strict_mode: bool) -> PyResult<Self> {
         // Strict Mode: Check for Forbidden Input Zones
         if strict_mode {
             for inp in &inputs {
                 let root = inp.split('.').next().unwrap_or(inp);
                 if ["SIG", "CMD", "META"].contains(&root.to_uppercase().as_str()) {
                     return Err(PyPermissionError::new_err(
                         format!("SECURITY VIOLATION: Using Control Plane '{}' as input is forbidden in Strict Mode.", root)
                     ));
                 }
             }
         }

         Ok(ContextGuard {
            target,
            allowed_inputs: inputs,
            allowed_outputs: outputs,
            path_prefix: "".to_string(),
            tx,
            is_admin,
            strict_mode,
        })
    }

    fn check_permissions(&self, full_path: &str, is_write: bool) -> PyResult<()> {
        if self.is_admin { return Ok(()); }
        
        let is_ok = if is_write {
             self.allowed_outputs.iter().any(|rule| {
                rule == full_path || 
                rule.starts_with(&format!("{}.", full_path)) || 
                full_path.starts_with(&format!("{}.", rule)) || 
                full_path.starts_with(&format!("{}[", rule))
             })
        } else {
             // Read: Check Inputs OR Outputs (implicit read for output path traversal)
             self.allowed_inputs.iter().chain(self.allowed_outputs.iter()).any(|rule| {
                rule == full_path || 
                rule.starts_with(&format!("{}.", full_path)) || 
                full_path.starts_with(&format!("{}.", rule)) || 
                full_path.starts_with(&format!("{}[", rule))
             })
        };

        if !is_ok {
            let op = if is_write { "Write" } else { "Read" };
            return Err(PyPermissionError::new_err(format!("Illegal {}: '{}'", op, full_path)));
        }
        Ok(())
    }

    fn apply_guard(&self, py: Python, val: PyObject, full_path: String) -> PyResult<PyObject> {
        let val_bound = val.bind(py);
        let type_name = val_bound.get_type().name()?.to_string();

        if ["int", "float", "str", "bool", "NoneType"].contains(&type_name.as_str()) {
             return Ok(val);
        }

        if val_bound.is_callable() {
             return Ok(val);
        }

        // Check if Transaction is present
        // If NO Transaction (strict_mode=False), return raw value immediately
        let tx = match &self.tx {
            Some(t) => t,
            None => return Ok(val),
        };

        if type_name == "list" {
             let tx_bound = tx.bind(py);
             let shadow = tx_bound.borrow_mut().get_shadow(py, val.clone_ref(py), Some(full_path.clone()))?; 
             
             let can_write = self.check_permissions(&full_path, true).is_ok();
             let shadow_list = shadow.bind(py).downcast::<PyList>()?.clone().unbind();

             if can_write {
                 let tracked = TrackedList::new(shadow_list, tx.clone_ref(py), full_path);
                 return Ok(Py::new(py, tracked)?.into_py(py));
             } else {
                 let frozen = FrozenList::new(shadow_list);
                 return Ok(Py::new(py, frozen)?.into_py(py));
             }
        }

        if type_name == "dict" {
             let tx_bound = tx.bind(py);
             let shadow = tx_bound.borrow_mut().get_shadow(py, val.clone_ref(py), Some(full_path.clone()))?; 
             
             let can_write = self.check_permissions(&full_path, true).is_ok();
             let shadow_dict = shadow.bind(py).downcast::<PyDict>()?.clone().unbind();

             if can_write {
                 let tracked = TrackedDict::new(shadow_dict, tx.clone_ref(py), full_path);
                 return Ok(Py::new(py, tracked)?.into_py(py));
             } else {
                 let frozen = FrozenDict::new(shadow_dict);
                 return Ok(Py::new(py, frozen)?.into_py(py));
             }
        }
        
        let tx_bound = tx.bind(py);
        let shadow = tx_bound.borrow_mut().get_shadow(py, val.clone_ref(py), Some(full_path.clone()))?; 

        Ok(Py::new(py, ContextGuard {
            target: shadow,
            allowed_inputs: self.allowed_inputs.clone(),
            allowed_outputs: self.allowed_outputs.clone(),
            path_prefix: full_path,
            tx: Some(tx.clone_ref(py)),
            is_admin: self.is_admin,
            strict_mode: self.strict_mode,
        })?.into_py(py))
    }
}

#[pymethods]
impl ContextGuard {
    #[new]
    #[pyo3(signature = (target, inputs, outputs, tx, is_admin=false, strict_mode=false))]
    fn new(target: PyObject, inputs: Vec<String>, outputs: Vec<String>, tx: Option<Py<Transaction>>, is_admin: bool, strict_mode: bool) -> PyResult<Self> {
        Self::new_internal(target, inputs, outputs, tx, is_admin, strict_mode)
    }

    fn __getattr__(&self, py: Python, name: String) -> PyResult<PyObject> {
        // Private access block in Strict Mode
        if self.strict_mode && name.starts_with('_') {
             return Err(PyPermissionError::new_err(format!("Access to private attribute '{}' denied in Strict Mode", name)));
        }

        if name.starts_with("_") {
             return self.target.bind(py).getattr(name.as_str())?.extract();
        }

        let full_path = if self.path_prefix.is_empty() {
            name.clone()
        } else {
            format!("{}.{}", self.path_prefix, name)
        };

        self.check_permissions(&full_path, false)?;

        let val = self.target.bind(py).getattr(name.as_str())?.unbind();
        self.apply_guard(py, val, full_path)
    }

    fn __setattr__(&self, py: Python, name: String, value: PyObject) -> PyResult<()> {
        let full_path = if self.path_prefix.is_empty() {
            name.clone()
        } else {
            format!("{}.{}", self.path_prefix, name)
        };

        self.check_permissions(&full_path, true)?;

        let old_val = self.target.bind(py).getattr(name.as_str()).ok().map(|v| v.unbind());

        // Unwrap Tracked Objects & Nested Guards
        let mut value = value;
        if let Ok(inner) = value.bind(py).getattr("_target") {
             value = inner.unbind();
        } 
        else if let Ok(shadow) = value.bind(py).getattr("_data") {
             value = shadow.unbind();
        }
        
        let zone = resolve_zone(&name);
        
        // HEAVY Zone Optimization: Skip Transaction Logging for heavy data (Tensors, Blobs)
        if zone != ContextZone::Heavy {
            if let Some(tx) = &self.tx {
                let mut tx_ref = tx.bind(py).borrow_mut();
                tx_ref.log_internal(
                full_path.clone(),
                "SET".to_string(),
                Some(value.clone_ref(py)),
                old_val,
                Some(self.target.clone_ref(py)),
                Some(name.clone())
            );
            } // End if let Some(tx)
        }
        
        self.target.bind(py).setattr(name.as_str(), value)?;
        Ok(())
    }

    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        let target = self.target.bind(py);
        
        if let Ok(val_bound) = target.get_item(&key) {
            let val = val_bound.unbind();
            
            let full_path = if let Ok(idx) = key.extract::<isize>(py) {
                format!("{}[{}]", self.path_prefix, idx)
            } else {
                let key_str = key.to_string();
                if self.path_prefix.is_empty() {
                    key_str
                } else {
                    format!("{}.{}", self.path_prefix, key_str)
                }
            };
            
            self.check_permissions(&full_path, false)?;
            return self.apply_guard(py, val, full_path);
        }

        if let Ok(key_str) = key.extract::<String>(py) {
             return self.__getattr__(py, key_str);
        }
        
        target.get_item(&key).map(|v| v.unbind())
    }

    fn __setitem__(&self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
        let target = self.target.bind(py);
        
        if let Ok(key_str) = key.extract::<String>(py) {
             return self.__setattr__(py, key_str, value);
        }

        let full_path = if let Ok(idx) = key.extract::<isize>(py) {
            format!("{}[{}]", self.path_prefix, idx)
        } else {
            let key_str = key.to_string();
             format!("{}.{}", self.path_prefix, key_str)
        };

        self.check_permissions(&full_path, true)?;
        
        let mut value_to_set = value.clone_ref(py);
        if let Ok(inner) = value.bind(py).getattr("_target") {
             value_to_set = inner.unbind();
        } else if let Ok(shadow) = value.bind(py).getattr("_data") {
             value_to_set = shadow.unbind();
        }
        
        let old_val = target.get_item(&key).ok().map(|v| v.unbind());
        
        let zone = if let Ok(key_str) = key.extract::<String>(py) {
             resolve_zone(&key_str)
        } else {
             ContextZone::Data // Integer index -> default Data 
        };

        // HEAVY Zone Optimization
        if zone != ContextZone::Heavy {
            if let Some(tx) = &self.tx {
                let mut tx_ref = tx.bind(py).borrow_mut();
                tx_ref.log_internal(
                    full_path.clone(),
                    "SET_ITEM".to_string(), 
                    Some(value_to_set.clone_ref(py)),
                    old_val,
                    Some(self.target.clone_ref(py)),
                    Some(key.to_string())
                );
            }
        }

        target.set_item(key, value_to_set)?;
        Ok(())
    }

    fn __contains__(&self, py: Python, key: PyObject) -> PyResult<bool> {
        self.target.bind(py).contains(key)
    }

    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        let iter = self.target.bind(py).call_method0("__iter__")?;
        Ok(iter.unbind())
    }
}
