
use pyo3::prelude::*;
use pyo3::exceptions::PyPermissionError;
use pyo3::types::{PyList, PyDict};
use crate::engine::Transaction;
use crate::tracked::{TrackedList, FrozenList};
use crate::proxy::SupervisorProxy;
use crate::zones::{resolve_zone, ContextZone};

#[pyclass(module = "theus_core", dict, subclass)]
pub struct ContextGuard {
    #[pyo3(get, name = "_target")]
    target: PyObject,
    allowed_inputs: Vec<String>,
    allowed_outputs: Vec<String>,
    path_prefix: String,
    tx: Option<Py<Transaction>>, 
    is_admin: bool,
    strict_mode: bool,
    #[pyo3(get, set)]
    log: Option<PyObject>,
}

impl ContextGuard {
    pub fn new_internal(target: PyObject, inputs: Vec<String>, outputs: Vec<String>, path_prefix: String, tx: Option<Py<Transaction>>, is_admin: bool, strict_mode: bool) -> PyResult<Self> {
         // Strict Mode: Check for Forbidden Input Zones
         if strict_mode {
             for inp in &inputs {
                 let zone = resolve_zone(inp);
                 match zone {
                     ContextZone::Signal | ContextZone::Meta => {
                         return Err(PyPermissionError::new_err(
                             format!("SECURITY VIOLATION: Input '{}' belongs to restricted Control Zone {:?}.", inp, zone)
                         ));
                     },
                     _ => {}
                 }
             }
         }

         Ok(ContextGuard {
            target,
            allowed_inputs: inputs,
            allowed_outputs: outputs,
            path_prefix,
            tx,
            is_admin,
            strict_mode,
            log: None,
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
        // println!("DEBUG: apply_guard called for path: '{}'", full_path);
        // std::io::stdout().flush().unwrap();
        
        let val_bound = val.bind(py);
        let type_name = val_bound.get_type().name()?.to_string();

        // NOTE: Whitelist includes Numpy scalar types (float64, int64...) for framework robustness.
        // These are immutable and should not be wrapped by ContextGuard.
        if ["int", "float", "str", "bool", "NoneType", "float64", "float32", "int64", "int32", "int16", "int8", "uint64", "uint32", "uint16", "uint16", "uint8", "bool_"].contains(&type_name.as_str()) {
             return Ok(val);
        }

        if val_bound.is_callable() {
             return Ok(val);
        }

        // Check if Transaction is present
        // If NO Transaction (strict_mode=False), return raw value immediately
        let tx = match &self.tx {
            Some(t) => t,
            None => {
                // println!("DEBUG: No Transaction for guard path '{}', returning raw value", full_path);
                // std::io::stdout().flush().unwrap();
                return Ok(val); 
            },
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
             // println!("DEBUG: Dict detected at '{}'", full_path);
             // std::io::stdout().flush().unwrap();
             let can_write = self.check_permissions(&full_path, true).is_ok();
             let shadow = val; 
             let proxy = SupervisorProxy::new(
                 shadow, 
                 full_path,
                 !can_write, 
                 if can_write { Some(tx.clone_ref(py).into_py(py)) } else { None },
             );
             return Ok(Py::new(py, proxy)?.into_py(py));
        }

        // v3.1: Nested SupervisorProxy Upgrade (Object/Dict)
        // If the value is ALREADY a SupervisorProxy (from State.domain), unwrap it and re-wrap with Transaction
        if let Ok(target) = val_bound.getattr("supervisor_target") {
             // println!("DEBUG: SupervisorProxy detected at '{}' (Upgrading)", full_path);
             // std::io::stdout().flush().unwrap();
             
             let inner = target.unbind();
             
             // CRITICAL FIX: Must shadow the inner object before wrapping!
             // Unwrapped proxy points to Original State (Arc). We need a Transaction Copy.
             let tx_bound = tx.bind(py);
             let shadow = tx_bound.borrow_mut().get_shadow(py, inner, Some(full_path.clone()))?; 
             
             let can_write = self.check_permissions(&full_path, true).is_ok();
             
             let proxy = SupervisorProxy::new(
                 shadow, 
                 full_path.clone(),
                 !can_write,
                 if can_write { Some(tx.clone_ref(py).into_py(py)) } else { None },
             );
             return Ok(Py::new(py, proxy)?.into_py(py));
        } else {
             // println!("DEBUG: Regular Object detected at '{}': Type={}", full_path, type_name);
             // std::io::stdout().flush().unwrap();
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
            log: None,
        })?.into_py(py))
    }
}

#[pymethods]
impl ContextGuard {
    #[new]
    #[pyo3(signature = (target, inputs, outputs, path_prefix=None, tx=None, is_admin=false, strict_mode=false))]
    fn new(target: PyObject, inputs: &Bound<'_, PyAny>, outputs: &Bound<'_, PyAny>, path_prefix: Option<String>, tx: Option<Py<Transaction>>, is_admin: bool, strict_mode: bool) -> PyResult<Self> {
        let prefix = path_prefix.unwrap_or_default();
        
        let to_vec = |obj: &Bound<'_, PyAny>| -> PyResult<Vec<String>> {
            let mut result = Vec::new();
            if let Ok(iter) = obj.iter() {
                for item in iter {
                    result.push(item?.extract::<String>()?); 
                }
            } else {
                 return Err(pyo3::exceptions::PyTypeError::new_err("Expected iterable for inputs/outputs"));
            }
            Ok(result)
        };

        let inputs_vec = to_vec(inputs)?;
        let outputs_vec = to_vec(outputs)?;

        Self::new_internal(target, inputs_vec, outputs_vec, prefix, tx, is_admin, strict_mode)
    }

    fn __getattr__(&self, py: Python, name: String) -> PyResult<PyObject> {
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

    fn __setattr__(&mut self, py: Python, name: String, value: PyObject) -> PyResult<()> {
        if name == "log" {
             self.log = Some(value);
             return Ok(());
        }
        
        let full_path = if self.path_prefix.is_empty() {
            name.clone()
        } else {
            format!("{}.{}", self.path_prefix, name)
        };

        self.check_permissions(&full_path, true)?;

        let old_val = self.target.bind(py).getattr(name.as_str()).ok().map(|v| v.unbind());

        let mut value = value;
        if let Ok(nested) = value.bind(py).getattr("supervisor_target") {
             value = nested.unbind();
        } 
        else if let Ok(shadow) = value.bind(py).getattr("_data") {
             value = shadow.unbind();
        }
        
        let zone = resolve_zone(&name);
        
        if zone != ContextZone::Heavy {
            if let Some(tx) = &self.tx {
                let tx_ref = tx.bind(py).borrow_mut();
                tx_ref.log_internal(
                full_path.clone(),
                "SET".to_string(),
                Some(value.clone_ref(py)),
                old_val,
                Some(self.target.clone_ref(py)),
                Some(name.clone())
            )?;
            } 
        }
        
        if self.target.bind(py).is_instance_of::<PyDict>() {
             self.target.call_method1(py, "__setitem__", (name, value))?;
        } else {
             self.target.bind(py).setattr(name.as_str(), value)?;
        }
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

    fn __setitem__(&mut self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
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
        if let Ok(inner) = value.bind(py).getattr("supervisor_target") {
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

        if zone != ContextZone::Heavy {
            if let Some(tx) = &self.tx {
                let tx_ref = tx.bind(py).borrow_mut();
                tx_ref.log_internal(
                    full_path.clone(),
                    "SET_ITEM".to_string(), 
                    Some(value_to_set.clone_ref(py)),
                    old_val,
                    Some(self.target.clone_ref(py)),
                    Some(key.to_string())
                )?;
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
