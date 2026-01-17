use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use crate::engine::Transaction;

/// Immutable List Wrapper
#[pyclass(module = "theus_core")]
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
        let list = self.data.bind(py);
        Ok(list.get_item(index as usize)?.unbind())
    }
    
    fn __len__(&self, py: Python) -> PyResult<usize> {
        Ok(self.data.bind(py).len())
    }
    
    fn __str__(&self, py: Python) -> PyResult<String> {
        Ok(format!("FrozenList({})", self.data.bind(py)))
    }
    
    fn __repr__(&self, py: Python) -> PyResult<String> {
        self.__str__(py)
    }
}

/// Transaction-Tracked Dictionary
#[pyclass(module = "theus_core")]
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

    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
        // Just read from shadow
        let dict = self.data.bind(py);
        match dict.get_item(key)? {
            Some(v) => Ok(v.unbind()),
            None => Err(pyo3::exceptions::PyKeyError::new_err("Key not found")),
        }
    }
    
    fn __setitem__(&self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
        let dict = self.data.bind(py);
        
        let _old_val = dict.get_item(&key)?.map(|v| v.unbind());
        
        // Log change to Transaction
        let tx = self.tx.bind(py).borrow();
        tx.log_internal(self.path.clone(), "SET_ITEM".to_string(), Some(value.clone_ref(py)), _old_val, Some(self.data.clone_ref(py).into()), Some(key.to_string()))?;
        // But Transaction in engine.rs is missing this method. 
        // We must update engine.rs first or rely on python-side patching? No, this is Rust.
        // For now, update the shadow directly.
        
        dict.set_item(key, value)?;
        Ok(())
    }
    
    fn __delitem__(&self, py: Python, key: PyObject) -> PyResult<()> {
        let dict = self.data.bind(py);
        dict.del_item(key)?;
        Ok(())
    }
}

/// Transaction-Tracked List
#[pyclass(module = "theus_core")]
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
    
    fn __getitem__(&self, py: Python, index: isize) -> PyResult<PyObject> {
        let list = self.data.bind(py);
        Ok(list.get_item(index as usize)?.unbind())
    }
    
    fn __setitem__(&self, py: Python, index: isize, value: PyObject) -> PyResult<()> {
        let list = self.data.bind(py);
        let _old_val = list.get_item(index as usize).ok().map(|v| v.unbind());
        
        let tx = self.tx.bind(py).borrow();
        tx.log_internal(self.path.clone(), "SET_ITEM".to_string(), Some(value.clone_ref(py)), _old_val, Some(self.data.clone_ref(py).into()), Some(index.to_string()))?;
        
        list.set_item(index as usize, value)?;
        Ok(())
    }
    
    fn append(&self, py: Python, value: PyObject) -> PyResult<()> {
        let list = self.data.bind(py);
        
        let tx = self.tx.bind(py).borrow();
        tx.log_internal(self.path.clone(), "APPEND".to_string(), Some(value.clone_ref(py)), None, Some(self.data.clone_ref(py).into()), None)?;
        
        list.append(value)?;
        Ok(())
    }
}
