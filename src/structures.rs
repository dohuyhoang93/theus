use pyo3::prelude::*;
use pyo3::types::{PyList, PyDict};
use crate::delta::Transaction;

#[pyclass]
pub struct TrackedList {
    data: Py<PyList>,
    tx: Py<Transaction>,
    path: String,
}

#[pymethods]
impl TrackedList {
    #[new]
    pub fn new(data: Py<PyList>, tx: Py<Transaction>, path: String) -> Self {
        TrackedList { data, tx, path }
    }
    
    fn __getnewargs__(&self, py: Python) -> PyResult<PyObject> {
        Ok((self.data.clone_ref(py), self.tx.clone_ref(py), self.path.clone()).into_py(py))
    }

    fn normalize_index(&self, py: Python, index: isize) -> PyResult<usize> {
        let len = self.data.bind(py).len();
        let real_index = if index < 0 {
            (len as isize + index) as usize
        } else {
            index as usize
        };
        
        if real_index >= len {
             return Err(pyo3::exceptions::PyIndexError::new_err("list index out of range"));
        }
        Ok(real_index)
    }

    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        // Use generic get_item which supports Slices and Integers via PyAny
        // PyList::get_item only supports usize, so we must use PyAny
        let val = self.data.bind(py).as_any().get_item(&key)?.unbind();
        let val_type = val.bind(py).get_type().name()?.to_string();

        if val_type == "list" || val_type == "dict" {
             let mut tx_val = self.tx.bind(py).borrow_mut();
             let shadow = tx_val.get_shadow(py, val.clone_ref(py), None)?;
             
             // If key is Integer, we CAN update.
             if let Ok(idx) = key.extract::<usize>(py) {
                 if !shadow.is(&val) {
                     // Use PyList set_item for index (efficient)
                     self.data.bind(py).set_item(idx, shadow.clone_ref(py))?;
                 }
             }
             
             let key_str = key.to_string();
             let child_path = format!("{}[{}]", self.path, key_str);
             
             if val_type == "list" {
                 let child_list = shadow.bind(py).downcast::<PyList>()?.clone().unbind();
                 let tracked = TrackedList {
                     data: child_list,
                     tx: self.tx.clone_ref(py),
                     path: child_path
                 };
                 return Ok(Py::new(py, tracked)?.into_py(py));
             } else if val_type == "dict" {
                 let child_dict = shadow.bind(py).downcast::<PyDict>()?.clone().unbind();
                 let tracked = TrackedDict {
                     data: child_dict,
                     tx: self.tx.clone_ref(py),
                     path: child_path
                 };
                 return Ok(Py::new(py, tracked)?.into_py(py));
             }
        }
        
        Ok(val)
    }

    fn __setitem__(&self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
        // Use generic set_item
        let old_val = self.data.bind(py).as_any().get_item(&key).ok().map(|v| v.unbind());
        self.data.bind(py).as_any().set_item(&key, value.clone_ref(py))?;
        
        // Log
        let key_str = key.to_string();
        let entry_path = format!("{}[{}]", self.path, key_str);
        self.tx.bind(py).borrow_mut().log_internal(
            entry_path, 
            "SET".to_string(), 
            Some(value), 
            old_val, 
            None, 
            None
        );
        Ok(())
    }

    fn append(&self, py: Python, value: PyObject) -> PyResult<()> {
        self.data.bind(py).append(value.clone_ref(py))?;
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "APPEND".to_string(),
            Some(value),
            None,
            None,
            None
        );
        Ok(())
    }

    fn insert(&self, py: Python, index: isize, value: PyObject) -> PyResult<()> {
        self.data.bind(py).call_method1("insert", (index, value.clone_ref(py)))?;
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "INSERT".to_string(),
            Some(value), // Logging index is complex in this schema, simplified
            None,
            None,
            None
        );
        Ok(())
    }

    fn extend(&self, py: Python, values: PyObject) -> PyResult<()> {
        // values is iterable
        self.data.bind(py).call_method1("extend", (values.clone_ref(py),))?;
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "EXTEND".to_string(),
            Some(values),
            None,
            None,
            None
        );
        Ok(())
    }

    fn clear(&self, py: Python) -> PyResult<()> {
        self.data.bind(py).call_method0("clear")?;
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "CLEAR".to_string(),
            None,
            None,
            None,
            None
        );
        Ok(())
    }

    #[pyo3(signature = (key=None, reverse=false))]
    fn sort(&self, py: Python, key: Option<PyObject>, reverse: bool) -> PyResult<()> {
        let kwargs = PyDict::new_bound(py);
        if let Some(k) = key {
            kwargs.set_item("key", k)?;
        }
        kwargs.set_item("reverse", reverse)?;
        
        self.data.bind(py).call_method("sort", (), Some(&kwargs))?;
        
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "SORT".to_string(),
            None, // Function objects hard to log
            None,
            None,
            None
        );
        Ok(())
    }

    fn reverse(&self, py: Python) -> PyResult<()> {
        self.data.bind(py).call_method0("reverse")?;
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "REVERSE".to_string(),
            None,
            None,
            None,
            None
        );
        Ok(())
    }
    
    #[pyo3(signature = (index=None))]
    fn pop(&self, py: Python, index: Option<isize>) -> PyResult<PyObject> {
        let idx = index.unwrap_or(-1);
        let val = self.data.bind(py).call_method1("pop", (idx,))?.unbind();
        
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "POP".to_string(),
            Some(val.clone_ref(py)), 
            None,
            None,
            None
        );
        Ok(val)
    }

    fn __len__(&self, py: Python) -> PyResult<usize> {
        Ok(self.data.bind(py).len())
    }
    
    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        let iter = self.data.bind(py).call_method0("__iter__")?;
        Ok(iter.unbind())
    }
    
    fn __str__(&self, py: Python) -> PyResult<String> {
        Ok(self.data.bind(py).to_string())
    }

    fn __contains__(&self, py: Python, item: PyObject) -> PyResult<bool> {
        self.data.bind(py).contains(item)
    }

    
    // Pickle support
    fn __getstate__(&self, py: Python) -> PyResult<PyObject> {
        // Return (data, tx, path) tuple
        Ok((self.data.clone_ref(py), self.tx.clone_ref(py), self.path.clone()).into_py(py))
    }
    
    fn __setstate__(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let tuple = state.downcast_bound::<pyo3::types::PyTuple>(py)?;
        self.data = tuple.get_item(0)?.extract()?;
        self.tx = tuple.get_item(1)?.extract()?;
        self.path = tuple.get_item(2)?.extract()?;
        Ok(())
    }
}

#[pyclass]
pub struct TrackedDict {
    data: Py<PyDict>,
    tx: Py<Transaction>,
    path: String,
}

#[pymethods]
impl TrackedDict {
    #[new]
    pub fn new(data: Py<PyDict>, tx: Py<Transaction>, path: String) -> Self {
        TrackedDict { data, tx, path }
    }
    
    fn __getnewargs__(&self, py: Python) -> PyResult<PyObject> {
        Ok((self.data.clone_ref(py), self.tx.clone_ref(py), self.path.clone()).into_py(py))
    }

    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        let val = match self.data.bind(py).get_item(&key)? {
            Some(v) => v.unbind(),
            None => return Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        };
        
        let val_type = val.bind(py).get_type().name()?.to_string();

        if val_type == "list" || val_type == "dict" {
             let mut tx_val = self.tx.bind(py).borrow_mut();
             let shadow = tx_val.get_shadow(py, val.clone_ref(py), None)?;
             
             if !shadow.is(&val) {
                 self.data.bind(py).set_item(&key, shadow.clone_ref(py))?;
             }
             
             let key_str = key.to_string();
             let child_path = if key_str.chars().all(|c| c.is_alphanumeric() || c == '_') {
                 format!("{}.{}", self.path, key_str)
             } else {
                 format!("{}[{}]", self.path, key_str)
             };
             
             if val_type == "list" {
                 let child_list = shadow.bind(py).downcast::<PyList>()?.clone().unbind();
                 let tracked = TrackedList {
                     data: child_list,
                     tx: self.tx.clone_ref(py),
                     path: child_path
                 };
                 return Ok(Py::new(py, tracked)?.into_py(py));
             } else if val_type == "dict" {
                 let child_dict = shadow.bind(py).downcast::<PyDict>()?.clone().unbind();
                 let tracked = TrackedDict {
                     data: child_dict,
                     tx: self.tx.clone_ref(py),
                     path: child_path
                 };
                 return Ok(Py::new(py, tracked)?.into_py(py));
             }
        }
        Ok(val)
    }

    fn __setitem__(&self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
        let old_val = self.data.bind(py).get_item(&key)?.map(|v| v.unbind());
        self.data.bind(py).set_item(&key, value.clone_ref(py))?;
        
        // Log
        let key_str = key.to_string();
        let entry_path = if key_str.chars().all(|c| c.is_alphanumeric() || c == '_') {
             format!("{}.{}", self.path, key_str)
        } else {
             format!("{}[{}]", self.path, key_str)
        };
        
        self.tx.bind(py).borrow_mut().log_internal(
            entry_path, 
            "SET".to_string(), 
            Some(value), 
            old_val, 
            None, 
            None
        );
        Ok(())
    }
    
    fn __delitem__(&self, py: Python, key: PyObject) -> PyResult<()> {
        let old_val = match self.data.bind(py).get_item(&key)? {
            Some(v) => v.unbind(),
            None => return Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        };
        
        self.data.bind(py).del_item(&key)?;
        
        let key_str = key.to_string();
        let entry_path = if key_str.chars().all(|c| c.is_alphanumeric() || c == '_') {
             format!("{}.{}", self.path, key_str)
        } else {
             format!("{}[{}]", self.path, key_str)
        };
        
        self.tx.bind(py).borrow_mut().log_internal(
            entry_path,
            "REMOVE".to_string(),
            None,
            Some(old_val),
            None,
            None
        );
        Ok(())
    }

    fn __len__(&self, py: Python) -> PyResult<usize> {
        Ok(self.data.bind(py).len())
    }
    
    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        let iter = self.data.bind(py).call_method0("__iter__")?;
        Ok(iter.unbind())
    }
    
    fn items(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).items().into_py(py))
    }
    
    fn keys(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).keys().into_py(py))
    }
    
    fn values(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).values().into_py(py))
    }

    #[pyo3(signature = (key, default=None))]
    fn pop(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        // If key exists, log POP(val). If not and default provided, return default (no log). If not and no default, raise KeyError.
        let has_key = self.data.bind(py).contains(&key)?;
        if has_key {
            let val = self.data.bind(py).call_method1("pop", (&key,))?.unbind();
            
            let key_str = key.to_string();
            let entry_path = if key_str.chars().all(|c| c.is_alphanumeric() || c == '_') {
                 format!("{}.{}", self.path, key_str)
            } else {
                 format!("{}[{}]", self.path, key_str)
            };
            
            self.tx.bind(py).borrow_mut().log_internal(
                entry_path,
                "POP".to_string(),
                None,
                Some(val.clone_ref(py)),
                None,
                None
            );
            Ok(val)
        } else if let Some(d) = default {
            Ok(d)
        } else {
            Err(pyo3::exceptions::PyKeyError::new_err(key.to_string()))
        }
    }

    fn popitem(&self, py: Python) -> PyResult<PyObject> {
        // Returns (key, value) tuple
        let tuple = self.data.bind(py).call_method0("popitem")?.unbind();
        let tuple_bound = tuple.bind(py).downcast::<pyo3::types::PyTuple>()?;
        let key = tuple_bound.get_item(0)?;
        let val = tuple_bound.get_item(1)?;
        
        let key_str = key.to_string();
         let entry_path = if key_str.chars().all(|c| c.is_alphanumeric() || c == '_') {
                 format!("{}.{}", self.path, key_str)
            } else {
                 format!("{}[{}]", self.path, key_str)
            };
            
        self.tx.bind(py).borrow_mut().log_internal(
            entry_path,
            "POPITEM".to_string(),
            None,
            Some(val.into_py(py)),
            None,
            None
        );
        Ok(tuple)
    }

    fn clear(&self, py: Python) -> PyResult<()> {
        self.data.bind(py).call_method0("clear")?;
        self.tx.bind(py).borrow_mut().log_internal(
            self.path.clone(),
            "CLEAR".to_string(),
            None,
            None,
            None,
            None
        );
        Ok(())
    }

    #[pyo3(signature = (key, default=None))]
    fn setdefault(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
        if self.data.bind(py).contains(&key)? {
             let val = self.data.bind(py).get_item(&key)?.unwrap().unbind();
             Ok(val)
        } else {
             let def_val = default.unwrap_or_else(|| py.None());
             // Reuse logging logic via __setitem__ helper or duplicate?
             // Since we are inside the class, we can call self.__setitem__?
             // Rust methods on PyClass are not inherent methods on the struct unless implemented that way.
             // We can just do the logic.
             
             self.data.bind(py).set_item(&key, def_val.clone_ref(py))?;
             
             let key_str = key.to_string();
             let entry_path = if key_str.chars().all(|c| c.is_alphanumeric() || c == '_') {
                  format!("{}.{}", self.path, key_str)
             } else {
                  format!("{}[{}]", self.path, key_str)
             };
             
             self.tx.bind(py).borrow_mut().log_internal(
                 entry_path, 
                 "SET".to_string(), 
                 Some(def_val.clone_ref(py)), 
                 None, // Old value is None
                 None, 
                 None
             );
             Ok(def_val)
        }
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
         // Re-use __getitem__ logic if possible, or simple delegation?
         // __getitem__ has wrapping logic. We want that.
         if self.data.bind(py).contains(&key)? {
             self.__getitem__(py, key)
         } else {
             Ok(default.unwrap_or_else(|| py.None()))
         }
    }
    
    #[pyo3(signature = (other))]
    fn update(&self, py: Python, other: PyObject) -> PyResult<()> {
        // Complex: Iterating and setting is best to ensure logging.
        // Or delegate to data.update() but then we lose granular logs?
        // Yes. For correctness, we must iterate.
        let other_dict = other.downcast_bound::<PyDict>(py)?;
        for (k, v) in other_dict {
             self.__setitem__(py, k.into_py(py), v.into_py(py))?;
        }
        Ok(())
    }

    fn __contains__(&self, py: Python, key: PyObject) -> PyResult<bool> {
        self.data.bind(py).contains(key)
    }


    fn __str__(&self, py: Python) -> PyResult<String> {
        Ok(self.data.bind(py).to_string())
    }
    
    // Pickle support
    fn __getstate__(&self, py: Python) -> PyResult<PyObject> {
        Ok((self.data.clone_ref(py), self.tx.clone_ref(py), self.path.clone()).into_py(py))
    }
    
    fn __setstate__(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let tuple = state.downcast_bound::<pyo3::types::PyTuple>(py)?;
        self.data = tuple.get_item(0)?.extract()?;
        self.tx = tuple.get_item(1)?.extract()?;
        self.path = tuple.get_item(2)?.extract()?;
        Ok(())
    }
}

// Frozen Structures

#[pyclass]
pub struct FrozenList {
    data: Py<PyList>,
}

#[pymethods]
impl FrozenList {
    #[new]
    pub fn new(data: Py<PyList>) -> Self {
        FrozenList { data }
    }

    fn __getitem__(&self, py: Python, index: isize) -> PyResult<PyObject> {
        let val = self.data.bind(py).get_item(index.try_into().unwrap_or(0))?.unbind(); // Quick fix for now or use normalize_index logic
        // For Frozen, we should recursively return Frozen items?
        // Yes, to maintain read-only property.
        let val_type = val.bind(py).get_type().name()?.to_string();
        
        if val_type == "list" {
             let child = val.bind(py).downcast::<PyList>()?.clone().unbind();
             return Ok(Py::new(py, FrozenList { data: child })?.into_py(py));
        } else if val_type == "dict" {
             let child = val.bind(py).downcast::<PyDict>()?.clone().unbind();
             return Ok(Py::new(py, FrozenDict { data: child })?.into_py(py));
        }
        Ok(val)
    }
    
    fn __setitem__(&self, _py: Python, _index: isize, _value: PyObject) -> PyResult<()> {
        Err(pyo3::exceptions::PyTypeError::new_err("'FrozenList' object does not support item assignment"))
    }
    
    fn append(&self, _py: Python, _value: PyObject) -> PyResult<()> {
        Err(pyo3::exceptions::PyTypeError::new_err("'FrozenList' object is immutable"))
    }

    fn __len__(&self, py: Python) -> PyResult<usize> {
        Ok(self.data.bind(py).len())
    }
    
    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        let iter = self.data.bind(py).call_method0("__iter__")?;
        Ok(iter.unbind())
    }
    
    fn __str__(&self, py: Python) -> PyResult<String> {
         Ok(format!("FrozenList({})", self.data.bind(py)))
    }

    fn __contains__(&self, py: Python, item: PyObject) -> PyResult<bool> {
        self.data.bind(py).contains(item)
    }

}

#[pyclass]
pub struct FrozenDict {
    data: Py<PyDict>,
}

#[pymethods]
impl FrozenDict {
    #[new]
    pub fn new(data: Py<PyDict>) -> Self {
        FrozenDict { data }
    }

    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        let val = match self.data.bind(py).get_item(&key)? {
            Some(v) => v.unbind(),
            None => return Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        };
        
        let val_type = val.bind(py).get_type().name()?.to_string();
        
        if val_type == "list" {
             let child = val.bind(py).downcast::<PyList>()?.clone().unbind();
             return Ok(Py::new(py, FrozenList { data: child })?.into_py(py));
        } else if val_type == "dict" {
             let child = val.bind(py).downcast::<PyDict>()?.clone().unbind();
             return Ok(Py::new(py, FrozenDict { data: child })?.into_py(py));
        }
        Ok(val)
    }
    
    fn __setitem__(&self, _py: Python, _key: PyObject, _value: PyObject) -> PyResult<()> {
        Err(pyo3::exceptions::PyTypeError::new_err("'FrozenDict' object does not support item assignment"))
    }
    
    fn __len__(&self, py: Python) -> PyResult<usize> {
        Ok(self.data.bind(py).len())
    }
    
    fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        let iter = self.data.bind(py).call_method0("__iter__")?;
        Ok(iter.unbind())
    }
    
    fn items(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).items().into_py(py))
    }
    
    fn keys(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).keys().into_py(py))
    }
    
    fn values(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).values().into_py(py))
    }

    #[pyo3(signature = (key, default=None))]
    fn get(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
         if self.data.bind(py).contains(&key)? {
             self.__getitem__(py, key)
         } else {
             Ok(default.unwrap_or_else(|| py.None()))
         }
    }

    fn __contains__(&self, py: Python, key: PyObject) -> PyResult<bool> {
        self.data.bind(py).contains(key)
    }


    fn __str__(&self, py: Python) -> PyResult<String> {
         Ok(format!("FrozenDict({})", self.data.bind(py)))
    }
}
