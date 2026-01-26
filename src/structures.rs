use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::create_exception;
use crate::proxy::SupervisorProxy;
use im::HashMap;
use std::sync::{Arc, Mutex};
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};
use crate::signals::SignalHub;
use crate::engine::Transaction;

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
        match self.__getitem__(py, name) {
            Ok(v) => Ok(v),
            Err(_) => Err(pyo3::exceptions::PyAttributeError::new_err("Attribute not found")),
        }
    }

    fn to_dict(&self, py: Python) -> Py<PyDict> {
        self.data.clone_ref(py)
    }

    fn keys(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.data.bind(py).keys().into())
    }

    fn __deepcopy__(&self, py: Python, memo: PyObject) -> PyResult<PyObject> {
        let copy_mod = py.import("copy")?;
        let deepcopy = copy_mod.getattr("deepcopy")?;
        // Deepcopy internal dict
        let copied_data = deepcopy.call1((self.data.bind(py), memo))?; 
        // Return new FrozenDict
        let new_dict = copied_data.downcast_into::<PyDict>()?.unbind();
        Ok(Py::new(py, FrozenDict { data: new_dict })?.into_any())
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
    // v3.3: Key-Level Versioning for Smart CAS
    pub key_last_modified: HashMap<String, u64>,
    // v3.3: Signal Latch for Flux (Snapshot of signals in this version)
    pub last_signals: HashMap<String, String>,
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
        let mut key_last_mod = HashMap::new();
        let last_sig = HashMap::new(); // Init empty latch

        if let Some(d) = data {
            let d_dict = d.downcast_bound::<PyDict>(py)?;
            for (k, v) in d_dict {
                let key = k.extract::<String>()?;
                state_data.insert(key.clone(), Arc::new(v.into_py(py)));
                key_last_mod.insert(key, version);
            }
        }

        if let Some(h) = heavy {
            let h_dict = h.downcast_bound::<PyDict>(py)?;
            for (k, v) in h_dict {
                 let key = k.extract::<String>()?;
                 state_heavy.insert(key.clone(), Arc::new(v.into_py(py)));
                 key_last_mod.insert(key, version);
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
            key_last_modified: key_last_mod,
            last_signals: last_sig,
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
            key_last_modified: self.key_last_modified.clone(),
            last_signals: HashMap::new(), // Reset latch for new tick
        };

        // Auto-log update event (Meta Zone)
        new_state.log_meta("state_update", &format!("State updated to version {}", new_state.version));

        if let Some(d) = data {
            let d_dict = d.downcast_bound::<PyDict>(py)?;
            for (k, v) in d_dict {
                let zone_key = k.extract::<String>()?;
                
                // v3.1: Track NESTED field paths for Field-Level CAS
                // NOTE: Must downcast BEFORE into_py to avoid borrow-after-move
                if let Ok(inner_dict) = v.downcast::<PyDict>() {
                    for (ik, _iv) in inner_dict {
                        let inner_key = ik.extract::<String>()?;
                        let field_path = format!("{}.{}", zone_key, inner_key);  // "domain.counter"
                        new_state.key_last_modified.insert(field_path, new_state.version);
                    }
                }
                
                // Keep zone-level tracking for backwards compatibility
                new_state.key_last_modified.insert(zone_key.clone(), new_state.version);
                new_state.data.insert(zone_key, Arc::new(v.into_py(py)));
            }
        }
        
        if let Some(h) = heavy {
            let h_dict = h.downcast_bound::<PyDict>(py)?;
            for (k, v) in h_dict {
                let zone_key = k.extract::<String>()?;
                
                // v3.1: Track NESTED field paths for Field-Level CAS
                // NOTE: Must downcast BEFORE into_py to avoid borrow-after-move
                if let Ok(inner_dict) = v.downcast::<PyDict>() {
                    for (ik, _iv) in inner_dict {
                        let inner_key = ik.extract::<String>()?;
                        let field_path = format!("{}.{}", zone_key, inner_key);  // "heavy.buffer"
                        new_state.key_last_modified.insert(field_path, new_state.version);
                    }
                }
                
                // Keep zone-level tracking for backwards compatibility
                new_state.key_last_modified.insert(zone_key.clone(), new_state.version);
                new_state.heavy.insert(zone_key, Arc::new(v.into_py(py)));
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
                        // Latch for Flux
                        new_state.last_signals.insert(topic, payload);
                     }
                }
            } else if let Ok(s_dict) = s.downcast_bound::<PyDict>(py) {
                 for (k, v) in s_dict {
                    let topic = k.extract::<String>()?;
                    let payload = v.to_string(); 
                    new_state.signal.publish(format!("{}:{}", topic, payload));
                    // Latch for Flux
                    new_state.last_signals.insert(topic, payload);
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
            key_last_modified: self.key_last_modified.clone(),
            last_signals: self.last_signals.clone(),
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
    fn signals(&self, py: Python) -> PyResult<PyObject> {
        // Expose Latched Signals as Dict for Flux
        let dict = PyDict::new_bound(py);
        for (k, v) in &self.last_signals {
            dict.set_item(k, v)?;
        }
        let frozen = Py::new(py, FrozenDict::new(dict.unbind()))?;
        Ok(frozen.into_py(py))
    }

    #[getter]
    fn domain(&self, py: Python) -> PyResult<PyObject> {
        match self.data.get("domain") {
             Some(val) => {
                 // v3.1: Return SupervisorProxy (Read-Only) by default
                 // This allows ContextGuard to "upgrade" it to Mutable if Transaction exists
                 // while preserving legacy read-only behavior for direct access.
                 let proxy = SupervisorProxy::new(
                     val.clone_ref(py),
                     "domain".to_string(),
                     true, // Read-Only
                     None,
                 );
                 Ok(Py::new(py, proxy)?.into_py(py))
             },
             None => Ok(py.None())
        }
    }

    /// v3.1: Returns domain wrapped in SupervisorProxy (preserves PyObject idiomatics)
    fn domain_proxy(&self, py: Python, read_only: Option<bool>) -> PyResult<PyObject> {
        match self.data.get("domain") {
            Some(val) => {
                let proxy = SupervisorProxy::new(
                    val.clone_ref(py),
                    "domain".to_string(),
                    read_only.unwrap_or(false),
                    None,
                );
                Ok(Py::new(py, proxy)?.into_py(py))
            },
            None => Ok(py.None())
        }
    }

    #[getter]
    fn global(&self, py: Python) -> PyResult<PyObject> {
        match self.data.get("global") {
             Some(val) => {
                 let proxy = SupervisorProxy::new(
                     val.clone_ref(py),
                     "global".to_string(),
                     true, // Read-Only
                     None,
                 );
                 Ok(Py::new(py, proxy)?.into_py(py))
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
    #[pyo3(get)]
    pub tx: Option<Py<Transaction>>, // v3.1: Expose active transaction
}

#[pymethods]
impl ProcessContext {
    #[new]
    fn new(state: Py<State>, local: Py<PyDict>, tx: Option<Py<Transaction>>) -> Self {
        ProcessContext { 
            state, 
            local,
            outbox: Outbox::new(), 
            tx,
        }
    }

    // v3.2 Safe Alias: global_ctx -> state.getattr("global")
    // Use this because 'global' is a reserved keyword in Python!
    #[getter]
    fn global_ctx(&self, py: Python) -> PyResult<PyObject> {
        let state_bound = self.state.bind(py);
        state_bound.getattr("global")?.extract()
    }

    // v3.2 Safe Alias: domain_ctx -> state.getattr("domain")
    #[getter]
    fn domain_ctx(&self, py: Python) -> PyResult<PyObject> {
        let state_bound = self.state.bind(py);
        state_bound.getattr("domain")?.extract()
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
