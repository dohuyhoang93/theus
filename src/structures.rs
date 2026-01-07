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

    fn __getitem__(&self, py: Python, index: isize) -> PyResult<PyObject> {
        let idx = self.normalize_index(py, index)?;
        let val = self.data.bind(py).get_item(idx)?.unbind();
        let val_type = val.bind(py).get_type().name()?.to_string();

        if val_type == "list" || val_type == "dict" {
             let mut tx_val = self.tx.bind(py).borrow_mut();
             let shadow = tx_val.get_shadow(py, val.clone_ref(py), None)?;
             
             if !shadow.is(&val) {
                 self.data.bind(py).set_item(idx, shadow.clone_ref(py))?;
             }
             
             let child_path = format!("{}[{}]", self.path, index);
             
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

    fn __setitem__(&self, py: Python, index: isize, value: PyObject) -> PyResult<()> {
        let idx = self.normalize_index(py, index)?;
        let old_val = self.data.bind(py).get_item(idx)?.unbind();
        self.data.bind(py).set_item(idx, value.clone_ref(py))?;
        
        // Log
        let entry_path = format!("{}[{}]", self.path, index);
        self.tx.bind(py).borrow_mut().log_internal(
            entry_path, 
            "SET".to_string(), 
            Some(value), 
            Some(old_val), 
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
