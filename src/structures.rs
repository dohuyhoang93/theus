use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::create_exception;
use im::HashMap;
use std::sync::{Arc, Mutex};
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};
use crate::signals::SignalHub;

create_exception!(theus.structures, ContextError, pyo3::exceptions::PyException);

#[pyclass(module = "theus_core")]
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
        match self.data.bind(py).get_item(key)? {
            Some(v) => Ok(v.unbind()),
            None => Err(pyo3::exceptions::PyKeyError::new_err("Key not found")),
        }
    }
    
    fn __setitem__(&self, _py: Python, _key: PyObject, _val: PyObject) -> PyResult<()> {
        Err(ContextError::new_err("Context is Immutable. Use .update()"))
    }
    
    fn __str__(&self, py: Python) -> PyResult<String> {
        Ok(format!("FrozenDict({})", self.data.bind(py)))
    }
    
    fn get(&self, py: Python, key: PyObject, default: Option<PyObject>) -> PyResult<PyObject> {
         if let Some(v) = self.data.bind(py).get_item(key)? {
             Ok(v.unbind())
         } else {
             Ok(default.unwrap_or_else(|| py.None()))
         }
    }

    fn __getattr__(&self, py: Python, name: PyObject) -> PyResult<PyObject> {
        self.__getitem__(py, name)
    }

    fn to_dict(&self, py: Python) -> Py<PyDict> {
        self.data.clone_ref(py)
    }

    fn keys(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).keys().into())
    }

    fn values(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).values().into())
    }

    fn items(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).items().into())
    }
}

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct MetaLogEntry {
    #[pyo3(get)]
    pub timestamp: f64,
    #[pyo3(get)]
    pub key: String,
    #[pyo3(get)]
    pub message: String,
}

#[pymethods]
impl MetaLogEntry {
    fn __repr__(&self) -> String {
        format!("MetaLogEntry(time={}, key={}, msg={})", self.timestamp, self.key, self.message)
    }
}

/// Theus v3 Immutable State

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct State {
    pub data: HashMap<String, Arc<PyObject>>,
    pub heavy: HashMap<String, Arc<PyObject>>, 
    pub signal: Arc<SignalHub>, // Revolution: Channel-based
    pub meta_logs: Arc<Mutex<VecDeque<MetaLogEntry>>>,
    pub meta_capacity: usize,
    pub version: u64,
}

#[pymethods]
impl State {
    #[new]
    #[pyo3(signature = (data=None, heavy=None, signal=None, version=1, meta_capacity=1000))]
    pub fn new(data: Option<PyObject>, heavy: Option<PyObject>, signal: Option<PyObject>, version: u64, meta_capacity: usize, py: Python) -> PyResult<Self> {
        let _ = signal; // Suppress unused warning
        let mut state_data = HashMap::new();
        let mut state_heavy = HashMap::new();
        
        // Signal logic changed: We ignore input dict for signal (legacy) or use it?
        // v3.2: Signal is transient. We create a fresh Hub unless one is passed (which is opaque).
        // For now, simpler: Always new Hub. 
        let state_signal = Arc::new(SignalHub::new());

        if let Some(d) = data {
            let d_dict = d.downcast_bound::<PyDict>(py)?;
            for (k, v) in d_dict {
                let key = k.extract::<String>()?;
                state_data.insert(key, Arc::new(v.into_py(py)));
            }
        }

        if let Some(h) = heavy {
            let h_dict = h.downcast_bound::<PyDict>(py)?;
            for (k, v) in h_dict {
                 let key = k.extract::<String>()?;
                 state_heavy.insert(key, Arc::new(v.into_py(py)));
            }
        }
        
        // Legacy signal dict is ignored in v3.2 to enforce Channel usage.
        // Or we could publish keys as initial messages? No, keep it clean.

        Ok(State {
            data: state_data,
            heavy: state_heavy,
            signal: state_signal,
            meta_logs: Arc::new(Mutex::new(VecDeque::with_capacity(meta_capacity))),
            meta_capacity,
            version,
        })
    }

    #[pyo3(signature = (data=None, heavy=None, signal=None))]
    fn update(&self, py: Python, data: Option<PyObject>, heavy: Option<PyObject>, signal: Option<PyObject>) -> PyResult<Self> {
        // In v3.2, 'signal' argument in update() is strictly used for firing events, 
        // NOT for changing the Hub structure. The Hub remains the same Arc across versions (Topology).
        
        let mut new_state = State {
            data: self.data.clone(),
            heavy: self.heavy.clone(),
            signal: self.signal.clone(), // Share same hub
            meta_logs: self.meta_logs.clone(),
            meta_capacity: self.meta_capacity,
            version: self.version + 1,
        };

        // Auto-log update event (Meta Zone)
        new_state.log_meta("state_update", &format!("State updated to version {}", new_state.version));

        if let Some(d) = data {
            let d_dict = d.downcast_bound::<PyDict>(py)?;
            for (k, v) in d_dict {
                let key = k.extract::<String>()?;
                new_state.data.insert(key, Arc::new(v.into_py(py)));
            }
        }
        
        if let Some(h) = heavy {
            let h_dict = h.downcast_bound::<PyDict>(py)?;
            for (k, v) in h_dict {
                let key = k.extract::<String>()?;
                new_state.heavy.insert(key, Arc::new(v.into_py(py)));
            }
        }
        
        if let Some(s) = signal {
            // Polymorphic handling: PyList (Batch from Transaction) or PyDict (Single update)
            if let Ok(s_list) = s.downcast_bound::<PyList>(py) {
                for item in s_list {
                     let s_dict = item.downcast::<PyDict>()?;
                     for (k, v) in s_dict {
                        let topic = k.extract::<String>()?;
                        let payload = v.to_string(); 
                        new_state.signal.publish(format!("{}:{}", topic, payload));
                     }
                }
            } else if let Ok(s_dict) = s.downcast_bound::<PyDict>(py) {
                 for (k, v) in s_dict {
                    let topic = k.extract::<String>()?;
                    let payload = v.to_string(); 
                    new_state.signal.publish(format!("{}:{}", topic, payload));
                }
            }
        }
        
        Ok(new_state)
    }

    /// Log a system event to the Meta Zone Ring Buffer.
    fn log_meta(&self, key: &str, message: &str) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let entry = MetaLogEntry {
            timestamp: now,
            key: key.to_string(),
            message: message.to_string(),
        };

        let mut logs = self.meta_logs.lock().unwrap();
        if logs.len() >= self.meta_capacity && self.meta_capacity > 0 {
            logs.pop_front();
        }
        if self.meta_capacity > 0 {
            logs.push_back(entry);
        }
    }

    /// Retrieve persistent meta logs (shared across state versions).
    fn get_meta_logs(&self) -> Vec<MetaLogEntry> {
        self.meta_logs.lock().unwrap().iter().cloned().collect()
    }

    fn restrict_view(&self) -> State {
        State {
            data: self.data.clone(),
            heavy: self.heavy.clone(),
            signal: Arc::new(SignalHub::new()), // Fix: Arc<SignalHub>
            meta_logs: self.meta_logs.clone(), // Share system logs
            meta_capacity: self.meta_capacity,
            version: self.version,
        }
    }

    #[getter]
    fn version(&self) -> u64 {
        self.version
    }

    #[getter]
    fn data(&self, py: Python) -> PyResult<PyObject> {
        let dict = PyDict::new_bound(py);
        for (k, v) in &self.data {
            dict.set_item(k, v.as_ref())?;
        }
        let frozen = Py::new(py, FrozenDict::new(dict.unbind()))?;
        Ok(frozen.into_py(py))
    }
    
    #[getter]
    fn heavy(&self, py: Python) -> PyResult<PyObject> {
        let dict = PyDict::new_bound(py);
        for (k, v) in &self.heavy {
            dict.set_item(k, v.as_ref())?;
        }
         let frozen = Py::new(py, FrozenDict::new(dict.unbind()))?;
        Ok(frozen.into_py(py))
    }
    
    #[getter]
    fn signal(&self, py: Python) -> PyResult<PyObject> {
         // v3.2: Return the SignalHub directly
         // Create a new Python wrapper for the cloned SignalHub struct
         let hub = Py::new(py, (*self.signal).clone())?;
         Ok(hub.into_py(py))
    }

    #[getter]
    fn domain(&self, py: Python) -> PyResult<PyObject> {
        match self.data.get("domain") {
             Some(val) => {
                 // If val is a dict, wrap in FrozenDict for dot access
                 if val.bind(py).is_instance_of::<PyDict>() {
                     let dict: Py<PyDict> = val.extract(py)?;
                     let frozen = Py::new(py, FrozenDict::new(dict))?;
                     Ok(frozen.into_py(py))
                 } else {
                     Ok(val.clone_ref(py))
                 }
             },
             None => Ok(py.None())
        }
    }

    #[getter]
    fn global(&self, py: Python) -> PyResult<PyObject> {
        match self.data.get("global") {
             Some(val) => {
                 if val.bind(py).is_instance_of::<PyDict>() {
                     let dict: Py<PyDict> = val.extract(py)?;
                     let frozen = Py::new(py, FrozenDict::new(dict))?;
                     Ok(frozen.into_py(py))
                 } else {
                     Ok(val.clone_ref(py))
                 }
             },
             None => Ok(py.None())
        }
    }

    #[getter]
    fn meta(&self) -> Vec<MetaLogEntry> {
        self.get_meta_logs()
    }
    
    fn __setattr__(&self, _name: String, _value: PyObject) -> PyResult<()> {
        Err(ContextError::new_err("State is Immutable. Use .update() to create a new version."))
    }
}

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct Outbox {
    pub messages: Arc<Mutex<Vec<OutboxMsg>>>,
}

#[pymethods]
impl Outbox {
    #[new]
    fn new() -> Self {
        Outbox {
            messages: Arc::new(Mutex::new(Vec::new())),
        }
    }

    fn add(&self, msg: OutboxMsg) {
        self.messages.lock().unwrap().push(msg);
    }
    
    #[getter]
    fn get_messages(&self) -> Vec<OutboxMsg> {
        self.messages.lock().unwrap().clone()
    }
}

/// Ephemeral Context passed to Process
#[pyclass(module = "theus_core")]
pub struct ProcessContext {
    #[pyo3(get)]
    pub state: Py<State>,
    #[pyo3(get)]
    pub local: Py<PyDict>, // Mutable Ephemeral Scope
    #[pyo3(get)]
    pub outbox: Outbox,
}

#[pymethods]
impl ProcessContext {
    #[new]
    fn new(state: Py<State>, local: Py<PyDict>) -> Self {
        ProcessContext { 
            state, 
            local,
            outbox: Outbox::new(), 
        }
    }

    // Legacy Compatibility: global_ctx -> state.data["global"]
    #[getter]
    fn global_ctx(&self, py: Python) -> PyResult<PyObject> {
        let state_bound = self.state.bind(py);
        let data = state_bound.getattr("data")?;
        match data.get_item("global") {
            Ok(v) => Ok(v.unbind()),
            Err(_) => Ok(py.None()),
        }
    }

    // Legacy Compatibility: domain_ctx -> state.data["domain"]
    #[getter]
    fn domain_ctx(&self, py: Python) -> PyResult<PyObject> {
        let state_bound = self.state.bind(py);
        let data = state_bound.getattr("data")?;
        match data.get_item("domain") {
            Ok(v) => Ok(v.unbind()),
            Err(_) => Ok(py.None()),
        }
    }
    
    // Forward getter access to state (except local)
    fn __getattr__(&self, py: Python, name: String) -> PyResult<PyObject> {
        // First check state
        match self.state.bind(py).getattr(name.as_str()) {
            Ok(v) => Ok(v.unbind()),
            Err(_) => {
                // Return None or raise?
                Err(pyo3::exceptions::PyAttributeError::new_err(format!("'ProcessContext' object has no attribute '{}'", name)))
            }
        }
    }
}

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct OutboxMsg {
    #[pyo3(get)]
    pub topic: String,
    pub payload: Arc<PyObject>,
}

#[pymethods]
impl OutboxMsg {
    #[new]
    fn new(topic: String, payload: PyObject) -> Self {
        OutboxMsg { topic, payload: Arc::new(payload) }
    }

    #[getter]
    fn payload(&self, py: Python) -> PyObject {
        self.payload.as_ref().clone_ref(py)
    }
}
