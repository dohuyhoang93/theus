use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList};
use crate::structures::{State, ContextError, OutboxMsg};
use std::sync::{Arc, Mutex};
use std::time::Instant;

pyo3::create_exception!(theus_core, WriteTimeoutError, pyo3::exceptions::PyTimeoutError);

/// Helper to collect outbox messages in Transaction
#[pyclass(module = "theus_core")]
pub struct OutboxCollector {
    buffer: Arc<Mutex<Vec<OutboxMsg>>>,
}

#[pymethods]
impl OutboxCollector {
    fn add(&self, msg: OutboxMsg) {
        self.buffer.lock().unwrap().push(msg);
    }
}

#[pyclass(module = "theus_core", subclass)]
pub struct TheusEngine {
    state: Py<State>,
    outbox: Arc<Mutex<Vec<OutboxMsg>>>,
    worker: Arc<Mutex<Option<PyObject>>>,
    pub schema: Arc<Mutex<Option<PyObject>>>,
    pub audit_system: Arc<Mutex<Option<PyObject>>>, // NEW
    pub strict_mode: Arc<Mutex<bool>>,             // NEW
}

#[pymethods]
impl TheusEngine {
    #[new]
    fn new(py: Python) -> PyResult<Self> {
        let state = Py::new(py, State::new(None, None, None, 1, 1000, py)?)?;
        Ok(TheusEngine { 
            state,
            outbox: Arc::new(Mutex::new(Vec::new())),
            worker: Arc::new(Mutex::new(None)),
            schema: Arc::new(Mutex::new(None)),
            audit_system: Arc::new(Mutex::new(None)),
            strict_mode: Arc::new(Mutex::new(false)),
        })
    }
    
    fn set_audit_system(&self, audit: PyObject) {
        let mut a = self.audit_system.lock().unwrap();
        *a = Some(audit);
    }

    fn set_strict_mode(&self, strict: bool) {
        let mut s = self.strict_mode.lock().unwrap();
        *s = strict;
    }

    fn set_schema(&self, schema: PyObject) {
        let mut s = self.schema.lock().unwrap();
        *s = Some(schema);
    }
    
    #[getter]
    fn state(&self, py: Python) -> Py<State> {
        self.state.clone_ref(py)
    }

    // Return Transaction.
    #[pyo3(signature = (write_timeout_ms=5000))]
    fn transaction(slf: Py<TheusEngine>, py: Python, write_timeout_ms: u64) -> PyResult<Transaction> {
        Ok(Transaction {
            engine: slf,
            pending_data: PyDict::new_bound(py).unbind(),
            pending_heavy: PyDict::new_bound(py).unbind(),
            pending_signal: PyList::empty_bound(py).unbind(), // Fix: PyList
            pending_outbox: Arc::new(Mutex::new(Vec::new())),
            start_time: None,
            write_timeout_ms,
        })
    }

    fn commit_state(&mut self, state: Py<State>) {
        self.state = state;
    }
    
    fn attach_worker(&self, worker: PyObject) {
        let mut w = self.worker.lock().unwrap();
        *w = Some(worker);
    }
    
    fn process_outbox(&self, py: Python) -> PyResult<()> {
        let msgs: Vec<OutboxMsg>;
        {
            let mut q = self.outbox.lock().unwrap();
            if q.is_empty() {
                return Ok(());
            }
            msgs = q.drain(..).collect();
        }
        
        // Call worker
        let w_guard = self.worker.lock().unwrap();
        if let Some(ref worker) = *w_guard {
             for msg in msgs {
                 // Convert OutboxMsg to Python object? 
                 // It is a PyClass, so passing it is fine.
                 // We need to convert `msg` (Rust struct) to PyObject.
                 // OutboxMsg implements Clone.
                 // But `msg` is owned `OutboxMsg`. 
                 // To pass to Python, we wrap it in Py::new or into_py?
                 // Since OutboxMsg is #[pyclass(module = "theus_core")], we can create new Python instance.
                 let py_msg = Py::new(py, msg)?;
                 worker.call1(py, (py_msg,))?;
             }
        }
        Ok(())
    }

    #[pyo3(signature = (expected_version, data=None, heavy=None, signal=None))]
    fn compare_and_swap(
        &mut self, 
        py: Python, 
        expected_version: u64, 
        data: Option<PyObject>, 
        heavy: Option<PyObject>,
        signal: Option<PyObject>
    ) -> PyResult<()> {
        let current_state = self.state.bind(py);
        let current_version: u64 = current_state.getattr("version")?.extract()?;
        
        if current_version != expected_version {
            return Err(ContextError::new_err(format!(
                "CAS Version Mismatch: Expected {}, Found {}", 
                expected_version, current_version
            )));
        }

        let new_state_obj = current_state.call_method(
            "update", 
            (data, heavy, signal), 
            None
        )?;
        
        self.state = new_state_obj.extract::<Py<State>>()?;
        Ok(())
    }

    #[pyo3(signature = (name, func))]
    fn execute_process_async<'py>(
        &self, 
        py: Python<'py>, 
        name: String, 
        func: PyObject
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = name; 
        
        let inspect = py.import("inspect")?;
        let is_coroutine = inspect.call_method1("iscoroutinefunction", (&func,))?.is_truthy()?;
        
        // Create Ephemeral Context (RAII)
        // Create Ephemeral Context (RAII)
        let local_dict = PyDict::new_bound(py);
        
        // Fix: Use ProcessContext::new() constructor which handles Outbox init
        // Or init struct manually if ::new() is not accessible (it is private in structures.rs).
        // Since structures.rs has `pub struct ProcessContext`, fields are pub? 
        // No, in structures.rs fields are pub, but Outbox field added.
        // Let's check structures.rs again... yes `pub outbox: Outbox`.
        // So we can init manually.
        
        let ctx = Py::new(py, crate::structures::ProcessContext {
            state: self.state.clone_ref(py),
            local: local_dict.unbind(),
            outbox: crate::structures::Outbox {
                messages: Arc::new(Mutex::new(Vec::new()))
            }
        })?;

        let args = (ctx,);

        let coro_obj: PyObject = if is_coroutine {
            func.call1(py, args)?
        } else {
            let asyncio = py.import("asyncio")?;
            asyncio.call_method1("to_thread", (func, args.0))?.unbind()
        };
        
        Ok(coro_obj.bind(py).clone())
    }
}

// Transaction
// Removed duplicate `pyo3::types` import
// PyList should be imported at top level or merged.

// ... 

#[pyclass(module = "theus_core")]
pub struct Transaction {
    engine: Py<TheusEngine>,
    pending_data: Py<PyDict>,
    pending_heavy: Py<PyDict>,
    pending_signal: Py<PyList>, // Changed from PyDict to PyList
    pending_outbox: Arc<Mutex<Vec<OutboxMsg>>>,
    start_time: Option<Instant>,
    write_timeout_ms: u64,
}

#[pymethods]
impl Transaction {
    #[new]
    #[pyo3(signature = (engine=None, write_timeout_ms=5000))]
    fn new(py: Python, engine: Option<Py<TheusEngine>>, write_timeout_ms: u64) -> PyResult<Self> {
        let engine_obj = match engine {
            Some(e) => e,
            None => {
                let engine_struct = TheusEngine::new(py)?;
                Py::new(py, engine_struct)?
            }
        };

        Ok(Transaction {
            engine: engine_obj,
            pending_data: PyDict::new_bound(py).unbind(),
            pending_heavy: PyDict::new_bound(py).unbind(),
            pending_signal: PyList::empty_bound(py).unbind(), // Init empty list
            pending_outbox: Arc::new(Mutex::new(Vec::new())),
            start_time: None,
            write_timeout_ms,
        })
    }
    
    // ... getters ...
    #[getter]
    fn outbox(&self) -> OutboxCollector {
        OutboxCollector {
            buffer: self.pending_outbox.clone(),
        }
    }

    #[getter]
    fn write_timeout_ms(&self) -> u64 {
        self.write_timeout_ms
    }

    #[pyo3(signature = (data=None, heavy=None, signal=None))]
    fn update(&self, py: Python, data: Option<PyObject>, heavy: Option<PyObject>, signal: Option<PyObject>) -> PyResult<()> {
        if let Some(d) = data {
             let d_bound = d.bind(py);
             self.pending_data.bind(py).call_method1("update", (d_bound,))?;
        }
        if let Some(h) = heavy {
             let h_bound = h.bind(py);
             self.pending_heavy.bind(py).call_method1("update", (h_bound,))?;
        }
        if let Some(s) = signal {
             // For signals, we append the delta dict to the list to preserve sequence
             let s_bound = s.bind(py);
             self.pending_signal.bind(py).append(s_bound)?;
        }
        Ok(())
    }

    fn __enter__(mut slf: PyRefMut<Self>, _py: Python) -> PyResult<Py<Self>> {
        slf.start_time = Some(Instant::now());
        Ok(slf.into())
    }

    fn __exit__(
        &self, 
        py: Python, 
        _exc_type: Option<PyObject>, 
        _exc_value: Option<PyObject>, 
        _traceback: Option<PyObject>
    ) -> PyResult<()> {
        
        if _exc_type.is_some() {
            return Ok(());
        }

        // Enforce Timeout
        if let Some(start) = self.start_time {
             if start.elapsed().as_millis() as u64 > self.write_timeout_ms {
                 return Err(WriteTimeoutError::new_err(format!(
                     "Transaction timed out after {}ms (limit {}ms)", 
                     start.elapsed().as_millis(), 
                     self.write_timeout_ms
                 )));
             }
        }

        let engine = self.engine.bind(py);
        let current_state_obj = engine.getattr("state")?;
        
        // Optimistic Update: Create new state version
        let new_state_obj = current_state_obj.call_method(
            "update", 
            (self.pending_data.clone_ref(py), self.pending_heavy.clone_ref(py), self.pending_signal.clone_ref(py)), 
            None
        )?;

        // Schema Enforcement (Phase 32.2)
        {
             let engine_borrow = engine.borrow();
             let schema_guard = engine_borrow.schema.lock().unwrap();
             if let Some(ref schema) = *schema_guard {
                 // Convert State.data to Dict for Pydantic validation
                 // We validate the *Resulting* state data to ensure consistency.
                 
                 // Access property via getattr, not call_method
                 // Access property via getattr, not call_method
                 let frozen_data = new_state_obj.getattr("data")?;
                 let dict_data = frozen_data.call_method0("to_dict")?;
                 
                 // Pydantic model_validate
                 if let Err(e) = schema.call_method1(py, "model_validate", (dict_data,)) {
                      return Err(crate::config::SchemaViolationError::new_err(format!("Schema Violation: {}", e)));
                 }
             }
        }

        engine.call_method1("commit_state", (new_state_obj,))?;
        
        // Commit Outbox to Engine
        {
            let mut pending = self.pending_outbox.lock().unwrap();
            let msgs = pending.drain(..).collect::<Vec<_>>();
            
            // Access Engine Outbox
            let engine_ref = engine.borrow();
            engine_ref.outbox.lock().unwrap().extend(msgs);
        }

        Ok(())
    }

    /// Internal: Get shadow copy for CoW/Tracking
    pub fn get_shadow(&self, py: Python, val: PyObject, _path: Option<String>) -> PyResult<PyObject> {
        // Simple implementation: Deep copy
        let copy_module = py.import("copy")?;
        let shadow = copy_module.call_method1("deepcopy", (val,))?;
        Ok(shadow.unbind())
    }

    /// Internal: Log operation for Audit
    #[allow(clippy::too_many_arguments)]
    pub fn log_internal(
        &self, 
        _path: String, 
        _op: String, 
        _new_val: Option<PyObject>, 
        _old_val: Option<PyObject>, 
        _obj_ref: Option<PyObject>, 
        _key: Option<String>
    ) -> PyResult<()> {
        // Stub for audit logging from ContextGuard
        Ok(())
    }
}
