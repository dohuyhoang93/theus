use pyo3::{pyclass, pymethods, PyObject, PyResult, Python, Py};
use pyo3::gc::{PyVisit, PyTraverseError};
use pyo3::types::PyAnyMethods; // Fix for bind().repr() and call_method1
use crate::delta::Transaction;

/// Tier 2: Specialized Guard for Tensors (Numpy/Torch)
/// - Zero-copy arithmetic (Direct C-Dispatch)
/// - Bypass Transaction Log for values (Performance)
/// - Maintains Reference Logging (Audit)
#[pyclass(module = "theus_core")]
pub struct TheusTensorGuard {
    #[pyo3(get)]
    pub inner: PyObject,
    pub path: String,
    pub tx: Option<Py<Transaction>>,
}

#[pymethods]
impl TheusTensorGuard {
    #[new]
    pub fn new(inner: PyObject, path: String, tx: Option<Py<Transaction>>) -> Self {
        TheusTensorGuard { inner, path, tx }
    }

    // GC Support
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.inner)?;
        if let Some(tx) = &self.tx {
            visit.call(tx)?;
        }
        Ok(())
    }

    fn __clear__(&mut self) {
        // self.tx = None; 
    }

    // --- Attributes ---
    fn __getattr__(&self, py: Python, name: String) -> PyResult<PyObject> {
        // Direct dispatch for attributes (shape, dtype, data...)
        Ok(self.inner.bind(py).getattr(name.as_str())?.unbind())
    }
    
    // --- Container ---
    fn __len__(&self, py: Python) -> PyResult<usize> {
        self.inner.bind(py).len()
    }
    
    fn __getitem__(&self, py: Python, key: PyObject) -> PyResult<PyObject> {
         Ok(self.inner.bind(py).get_item(key)?.unbind())
    }
    
    fn __setitem__(&self, py: Python, key: PyObject, value: PyObject) -> PyResult<()> {
        if let Some(tx) = &self.tx {
             let mut tx_ref = tx.bind(py).borrow_mut();
             tx_ref.log_internal(
                self.path.clone(),
                "TENSOR_MUTATION".to_string(),
                None, 
                None,
                Some(self.inner.clone_ref(py)),
                Some(key.to_string())
            );
        }
        self.inner.bind(py).set_item(key, value)
    }

    // --- Arithmetic --
    fn __add__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__add__", (other,))?.unbind())
    }
    fn __radd__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__radd__", (other,))?.unbind())
    }

    fn __sub__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__sub__", (other,))?.unbind())
    }
    fn __rsub__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__rsub__", (other,))?.unbind())
    }
    
    fn __mul__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__mul__", (other,))?.unbind())
    }
    fn __rmul__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__rmul__", (other,))?.unbind())
    }
    
    fn __truediv__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__truediv__", (other,))?.unbind())
    }
    fn __rtruediv__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__rtruediv__", (other,))?.unbind())
    }
    
    // Comparison
    fn __lt__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__lt__", (other,))?.unbind())
    }
    fn __gt__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).call_method1("__gt__", (other,))?.unbind())
    }
    fn __le__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
         Ok(self.inner.bind(py).call_method1("__le__", (other,))?.unbind())
    }
    fn __ge__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
         Ok(self.inner.bind(py).call_method1("__ge__", (other,))?.unbind())
    }
    fn __eq__(&self, py: Python, other: PyObject) -> PyResult<PyObject> {
         Ok(self.inner.bind(py).call_method1("__eq__", (other,))?.unbind())
    }
    
    // Properties
    #[getter]
    fn shape(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).getattr("shape")?.unbind())
    }
    
    #[getter]
    fn dtype(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.inner.bind(py).getattr("dtype")?.unbind())
    }

    fn __repr__(&self, py: Python) -> PyResult<String> {
        Ok(format!("TheusTensorGuard(path='{}', inner={})", self.path, self.inner.bind(py).repr()?))
    }
}
