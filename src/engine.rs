use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList};
use crate::structures::{State, ContextError, OutboxMsg};
use crate::conflict::{ConflictManager, RetryDecision};
use std::sync::{Arc, Mutex};
use std::time::Instant;
use crate::structures_helper::set_nested_value;

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
    
    /// [v3.3] Drain all messages from the buffer for Python-side flush
    fn drain(&self) -> Vec<OutboxMsg> {
        self.buffer.lock().unwrap().drain(..).collect()
    }
    
    /// [v3.3] Get current message count
    fn len(&self) -> usize {
        self.buffer.lock().unwrap().len()
    }
}

#[pyclass(module = "theus_core", subclass)]
pub struct TheusEngine {
    state: Py<State>,
    outbox: Arc<Mutex<Vec<OutboxMsg>>>,
    worker: Arc<Mutex<Option<PyObject>>>,
    pub schema: Arc<Mutex<Option<PyObject>>>,
    pub audit_system: Arc<Mutex<Option<PyObject>>>, 
    pub strict_guards: Arc<Mutex<bool>>,             // NEW: I/O Policy
    pub strict_cas: Arc<Mutex<bool>>,                // NEW: Concurrency Policy
    conflict_manager: Arc<ConflictManager>,
}

#[pymethods]
impl TheusEngine {
    #[new]
    fn new(py: Python) -> PyResult<Self> {
        let state = Py::new(py, State::new(None, None, None, 0, 1000, py)?)?;
        Ok(TheusEngine { 
            state,
            outbox: Arc::new(Mutex::new(Vec::new())),
            worker: Arc::new(Mutex::new(None)),
            schema: Arc::new(Mutex::new(None)),
            audit_system: Arc::new(Mutex::new(None)),
            strict_guards: Arc::new(Mutex::new(false)),
            strict_cas: Arc::new(Mutex::new(false)),
            conflict_manager: Arc::new(ConflictManager::new(5, 2)), 
        })
    }
    
    fn set_audit_system(&self, audit: PyObject) {
        let mut a = self.audit_system.lock().unwrap();
        *a = Some(audit);
    }

    // Explicit Feature Toggles (POP Manifesto)
    fn set_strict_guards(&self, enabled: bool) {
        let mut s = self.strict_guards.lock().unwrap();
        *s = enabled;
    }

    fn set_strict_cas(&self, enabled: bool) {
        let mut s = self.strict_cas.lock().unwrap();
        *s = enabled;
    }

    fn set_schema(&self, schema: PyObject) {
        let mut s = self.schema.lock().unwrap();
        *s = Some(schema);
    }
    
    // Conflict APIs for Python Retry Loop
    fn report_conflict(&self, process_name: String) -> RetryDecision {
        self.conflict_manager.report_conflict(process_name)
    }

    fn report_success(&self, process_name: String) {
        self.conflict_manager.report_success(process_name);
    }
    
    #[getter]
    fn state(&self, py: Python) -> Py<State> {
        self.state.clone_ref(py)
    }

    /// [v3.3] Expose Engine Outbox for manual flushing
    #[getter]
    fn outbox(&self) -> OutboxCollector {
        OutboxCollector {
            buffer: self.outbox.clone(),
        }
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
            delta_log: Arc::new(Mutex::new(Vec::new())),
            shadow_cache: Arc::new(Mutex::new(std::collections::HashMap::new())),
            path_to_shadow: Arc::new(Mutex::new(std::collections::HashMap::new())),
            full_path_map: Arc::new(Mutex::new(std::collections::HashMap::new())),
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

    #[pyo3(signature = (expected_version, data=None, heavy=None, signal=None, requester=None))]
    fn compare_and_swap(
        &mut self, 
        py: Python, 
        expected_version: u64, 
        data: Option<PyObject>, 
        heavy: Option<PyObject>,
        signal: Option<PyObject>,
        requester: Option<String>
    ) -> PyResult<()> {
        // v3.3 Priority Ticket Check
        if self.conflict_manager.is_blocked(requester) {
             return Err(ContextError::new_err("System Busy (VIP Access Only)"));
        }

        // [FIX] Enforce Strict CAS if enabled (Explicit)
        let strict_cas = *self.strict_cas.lock().unwrap();
        
        let current_state_bound = self.state.bind(py);
        let current_state = current_state_bound.borrow();
        let current_version = current_state.version;
        
        if current_version != expected_version {
            if strict_cas {
                 return Err(ContextError::new_err(format!(
                    "Strict CAS Mismatch: Expected {}, Found {} (Strict CAS Enabled)", 
                    expected_version, current_version
                )));
            }

            // v3.3 Smart CAS: Check Key-Level Conflicts
            // If the specific keys we are updating haven't changed since expected_version,
            // we can safely merge even if global version bumped.
            
            let mut safe = true;
            
            // v3.1: Check FIELD-Level Conflicts (domain.counter, not just domain)
            // Check Data Keys
            if let Some(ref d) = data {
                if let Ok(d_dict) = d.downcast_bound::<PyDict>(py) {
                    for (zone_k, zone_v) in d_dict.iter() {
                         let zone_key = zone_k.extract::<String>()?;
                         
                         // Check nested fields if value is a dict
                         if let Ok(inner_dict) = zone_v.downcast::<PyDict>() {
                             for (ik, _) in inner_dict {
                                 let inner_key = ik.extract::<String>()?;
                                 let field_path = format!("{}.{}", zone_key, inner_key);  // "domain.counter"
                                 
                                 if let Some(last_ver) = current_state.key_last_modified.get(&field_path) {
                                     if *last_ver > expected_version {
                                         safe = false;
                                         break;
                                     }
                                 }
                             }
                         } else {
                             // Non-dict value: fall back to zone-level check
                             if let Some(last_ver) = current_state.key_last_modified.get(&zone_key) {
                                 if *last_ver > expected_version {
                                     safe = false;
                                 }
                             }
                         }
                         if !safe { break; }
                    }
                }
            }
            
            // Check Heavy Keys (if safe so far)
            if safe {
                if let Some(ref h) = heavy {
                    if let Ok(h_dict) = h.downcast_bound::<PyDict>(py) {
                        for (zone_k, zone_v) in h_dict.iter() {
                             let zone_key = zone_k.extract::<String>()?;
                             
                             // Check nested fields if value is a dict
                             if let Ok(inner_dict) = zone_v.downcast::<PyDict>() {
                                 for (ik, _) in inner_dict {
                                     let inner_key = ik.extract::<String>()?;
                                     let field_path = format!("{}.{}", zone_key, inner_key);
                                     
                                     if let Some(last_ver) = current_state.key_last_modified.get(&field_path) {
                                         if *last_ver > expected_version {
                                             safe = false;
                                             break;
                                         }
                                     }
                                 }
                             } else {
                                 // Non-dict value: fall back to zone-level check
                                 if let Some(last_ver) = current_state.key_last_modified.get(&zone_key) {
                                     if *last_ver > expected_version {
                                         safe = false;
                                     }
                                 }
                             }
                             if !safe { break; }
                        }
                    }
                }
            }

            if !safe {
                return Err(ContextError::new_err(format!(
                    "CAS Version Mismatch (Conflict Detected): Expected {}, Found {} (Keys Changed)", 
                    expected_version, current_version
                )));
            }
            // If safe, fall through to update (Optimistic Merge)
        }

        // We must drop the borrow before calling Python method `update` on the object
        // because `update` might need mutable access or create new object?
        // Actually `update` is a method on `State` which is immutable self.
        // But `call_method` might re-enter?
        // Safe practice: drop borrow.
        drop(current_state);


        let new_state_obj = current_state_bound.call_method(
            "update", 
            (data, heavy, signal), 
            None
        )?;

        // [v3.1.2] Schema Enforcement for CAS (Critical Gatekeeper)
        // Ensure new state is valid before replacing self.state
        {
             let schema_mutex = self.schema.lock().unwrap(); // Use separate var to avoid borrow conflict
             if let Some(ref schema) = *schema_mutex {
                 // Validate Resulting State
                 let frozen_data = new_state_obj.getattr("data")?;
                 let dict_data = frozen_data.call_method0("to_dict")?;
                 
                 if let Err(e) = schema.call_method1(py, "model_validate", (dict_data,)) {
                     // Reject Commit!
                     return Err(crate::config::SchemaViolationError::new_err(format!("Schema Violation (CAS): {}", e)));
                 }
             }
        }
        
        self.state = new_state_obj.extract::<Py<State>>()?;
        Ok(())
    }

    #[pyo3(signature = (name, func, tx=None))]
    fn execute_process_async<'py>(
        &self, 
        py: Python<'py>, 
        name: String, 
        func: PyObject,
        tx: Option<PyObject>
    ) -> PyResult<Bound<'py, PyAny>> {
        let _ = name; 
        
        let inspect = py.import("inspect")?;
        let is_coroutine = inspect.call_method1("iscoroutinefunction", (&func,))?.is_truthy()?;
        
        // if tx.is_some() { println!("DEBUG: execute_process_async with TX"); } else { println!("DEBUG: execute_process_async NO TX"); }

        // Create Ephemeral Context (RAII)
        let local_dict = PyDict::new_bound(py);
        
        let py_tx: Option<Py<Transaction>> = tx.map(|t| t.extract(py)).transpose()?;
        
        // [v3.3 Fix] Share Outbox Buffer with Transaction if present
        let outbox_buffer = if let Some(ref t) = py_tx {
            t.borrow(py).pending_outbox.clone()
        } else {
            Arc::new(Mutex::new(Vec::new()))
        };

        let ctx = Py::new(py, crate::structures::ProcessContext {
            state: self.state.clone_ref(py),
            local: local_dict.unbind(),
            outbox: crate::structures::Outbox {
                messages: outbox_buffer 
            },
            tx: py_tx, 
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
    // [v3.1 Zero Trust] Unified Delta Log
    pub delta_log: Arc<Mutex<Vec<crate::delta::DeltaEntry>>>, 
    pub shadow_cache: Arc<Mutex<std::collections::HashMap<usize, (PyObject, PyObject)>>>, // id -> (original, shadow)
    pub path_to_shadow: Arc<Mutex<std::collections::HashMap<String, PyObject>>>, // root -> shadow (for legacy commit)
    pub full_path_map: Arc<Mutex<std::collections::HashMap<String, PyObject>>>, // full_path -> shadow (for diff merging)
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
            delta_log: Arc::new(Mutex::new(Vec::new())),
            shadow_cache: Arc::new(Mutex::new(std::collections::HashMap::new())),
            path_to_shadow: Arc::new(Mutex::new(std::collections::HashMap::new())),
            full_path_map: Arc::new(Mutex::new(std::collections::HashMap::new())),
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

    // Expose pending data for manual commit/CAS
    #[getter]
    fn pending_data(&self, py: Python) -> PyObject {
        self.pending_data.clone_ref(py).into_py(py)
    }

    #[getter]
    fn pending_heavy(&self, py: Python) -> PyObject {
        self.pending_heavy.clone_ref(py).into_py(py)
    }

    #[getter]
    fn pending_signal(&self, py: Python) -> PyObject {
        self.pending_signal.clone_ref(py).into_py(py)
    }

    #[pyo3(signature = (data=None, heavy=None, signal=None))]
    fn update(&self, py: Python, data: Option<PyObject>, heavy: Option<PyObject>, signal: Option<PyObject>) -> PyResult<()> {
        if let Some(d) = data {
             let d_bound = d.bind(py);
             if let Ok(d_dict) = d_bound.downcast::<PyDict>() {
                 // [FIX v3.1.2] Use Deep In-Place Update to prevent "Silent Overwrite" within transaction
                 crate::structures_helper::deep_update_inplace(py, self.pending_data.bind(py), d_dict)?;
             } else {
                 return Err(ContextError::new_err("update data must be a dict"));
             }
        }
        if let Some(h) = heavy {
             let h_bound = h.bind(py);
             if let Ok(h_dict) = h_bound.downcast::<PyDict>() {
                 // [FIX v3.1.2] Deep In-Place Update for Heavy Zone too
                 crate::structures_helper::deep_update_inplace(py, self.pending_heavy.bind(py), h_dict)?;
             } else {
                 return Err(ContextError::new_err("heavy update data must be a dict"));
             }
        }
        if let Some(s) = signal {
             // For signals, we append the delta dict to the list to preserve sequence
             let s_bound = s.bind(py);
             self.pending_signal.bind(py).append(s_bound)?;
        }
        Ok(())
    }
    
    /// Get shadow updates keyed by root path (e.g., 'domain' -> shadow_dict)
    /// This extracts all modified root-level objects for committing to State.
    fn get_shadow_updates(&self, py: Python) -> PyResult<PyObject> {
        let result = PyDict::new_bound(py);
        let path_map = self.path_to_shadow.lock().unwrap();
        let delta_log = self.delta_log.lock().unwrap();
        
        // Collect unique root paths from delta_log (entries that were actually mutated)
        let mut modified_roots: std::collections::HashSet<String> = std::collections::HashSet::new();
        for entry in delta_log.iter() {
            let root = entry.path.split(['.', '[']).next().unwrap_or(&entry.path).to_string();
            modified_roots.insert(root);
        }
        
        // For each modified root, get its shadow from path_to_shadow
        for root in &modified_roots {
            if let Some(shadow) = path_map.get(root) {
                result.set_item(root.clone(), shadow.clone_ref(py))?;
            }
        }
        
        // Also merge explicit tx.update calls (pending_data)
        let pending = self.pending_data.bind(py);
        for kv in pending.iter() {
            let (k, v) = kv;
            result.set_item(k, v)?;
        }
        
        Ok(result.unbind().into_py(py))
    }

    /// [v3.1 Delta Replay] Build pending_data from delta_log by replaying mutations
    fn build_pending_from_deltas(&self, py: Python) -> PyResult<PyObject> {
        // [v3.1.2] Differential Shadow Merging: Infer Deltas from unlogged mutations
        self.infer_shadow_deltas(py)?;

        let result = PyDict::new_bound(py);
        let delta_log = self.delta_log.lock().unwrap();
        let result_py = result.clone().unbind().into_py(py);
        let result_dict: Py<pyo3::types::PyDict> = result_py.extract(py)?;
        
        for entry in delta_log.iter() {
            if let Some(ref val) = entry.value {
                let _ = crate::structures_helper::set_nested_value(py, &result_dict, &entry.path, &val.clone_ref(py).into_py(py));
            }
        }
        
        // Also merge explicit tx.update calls (pending_data)
        let pending = self.pending_data.bind(py);
        for kv in pending.iter() {
            let (k, v) = kv;
            result.set_item(k, v)?;
        }
        
        Ok(result.unbind().into_py(py))
    }

    /// [v3.1.2] Expose raw delta log for strict contract validation
    fn get_delta_log(&self, _py: Python) -> PyResult<Vec<String>> {
        let delta_log = self.delta_log.lock().unwrap();
        // Return only paths, values not needed for validation usually
        let paths: Vec<String> = delta_log.iter().map(|e| e.path.clone()).collect();
        Ok(paths)
    }

    /// [v3.3] Manual Flush for Flux Engine / execute()
    fn flush_outbox(&self, py: Python) -> PyResult<()> {
        let mut pending = self.pending_outbox.lock().unwrap();
        eprintln!("DEBUG: Transaction::flush_outbox pending_count={}", pending.len());
        if pending.is_empty() { return Ok(()); }
        
        let msgs = pending.drain(..).collect::<Vec<_>>();
        
        let engine = self.engine.bind(py);
        let engine_ref = engine.borrow();
        eprintln!("DEBUG: Transaction::flush_outbox transferring {} msgs to engine", msgs.len());
        engine_ref.outbox.lock().unwrap().extend(msgs);
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
        
        // [v3.1.2] Differential Shadow Merging:
        // 1. Infer mutations from shadows
        self.infer_shadow_deltas(py)?;
        // 2. Apply delta_log to pending_data
        self.commit(py)?;

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

    /// [v3.1.2] Infer Deltas from Shadow Mutations (Differential Merging)
    fn infer_shadow_deltas(&self, py: Python) -> PyResult<()> {
        // println!("DEBUG: infer_shadow_deltas EXECUTED"); 
        let path_map = self.full_path_map.lock().unwrap();
        let cache = self.shadow_cache.lock().unwrap();
        let mut new_deltas = Vec::new();

        for (path, shadow) in path_map.iter() {
            let shadow_id = shadow.bind(py).as_ptr() as usize;
            
            if let Some((original, _)) = cache.get(&shadow_id) {
                 if original.bind(py).as_ptr() == shadow.bind(py).as_ptr() {
                     continue;
                 }
                 
                 let are_equal = match original.bind(py).rich_compare(shadow.bind(py), pyo3::basic::CompareOp::Eq) {
                     Ok(res) => {
                         match res.is_truthy() {
                             Ok(b) => b,
                             Err(_) => {
                                 // Fallback for NumPy arrays: (a == b).all()
                                 res.call_method0("all").is_ok_and(|x| x.is_truthy().unwrap_or(false))
                             }
                         }
                     },
                     Err(_) => false // specific error handling skipped for brevity
                 };
                 
                 if !are_equal {
                     new_deltas.push(crate::delta::DeltaEntry {
                         path: path.clone(),
                         op: "SET".to_string(),
                         value: Some(shadow.clone_ref(py)),
                         old_value: Some(original.clone_ref(py)),
                         target: None,
                         key: None,
                     });
                 }
            }
        }
        
        let mut log = self.delta_log.lock().unwrap();
        log.extend(new_deltas);
        Ok(())
    }

    /// Internal: Get shadow copy for CoW/Tracking
    pub fn get_shadow(&self, py: Python, val: PyObject, path: Option<String>) -> PyResult<PyObject> {
        let id = val.bind(py).as_ptr() as usize;
        let mut cache = self.shadow_cache.lock().unwrap();
        
        if let Some((_, shadow)) = cache.get(&id) {
             // println!("[Theus] get_shadow CACHE HIT: {:?} -> {:?}", id, shadow.bind(py).as_ptr());
             return Ok(shadow.clone_ref(py));
        }

        // Heavy Zone Check (Skip copy if configured)
        if let Some(ref p) = path {
            if crate::zones::resolve_zone(p) == crate::zones::ContextZone::Heavy {
                  println!("[Theus] get_shadow HEAVY SKIP: {}", p);
                  cache.insert(id, (val.clone_ref(py), val.clone_ref(py)));
                  return Ok(val);
            }
        }

        // Deep Copy
        let copy_mod = py.import("copy")?;
        let shadow = match copy_mod.call_method1("deepcopy", (&val,)) { 
            Ok(s) => s.unbind(),
            Err(e) => {
                 eprintln!("[Theus] WARNING (DEBUG): Cannot copy object at {:?}: {}", path, e);
                 cache.insert(id, (val.clone_ref(py), val.clone_ref(py)));
                 return Ok(val);
            }
        };
        
        


        // Disable Legacy Lock Manager on Shadow
        let _ = shadow.bind(py).setattr("_lock_manager", py.None());
        
        let shadow_id = shadow.bind(py).as_ptr() as usize;
        
        // Track
        cache.insert(id, (val.clone_ref(py), shadow.clone_ref(py)));
        cache.insert(shadow_id, (val, shadow.clone_ref(py))); // Map shadow to itself to prevent re-shadowing
        
        // v3.1: Also store ROOT path -> shadow for commit retrieval
        if let Some(ref p) = path {
            let root = p.split(['.', '[']).next().unwrap_or(p).to_string();
            {
                let mut path_map = self.path_to_shadow.lock().unwrap();
                // Only insert if root not already present (preserve deeper shadows if multiple accesses)
                path_map.entry(root).or_insert_with(|| shadow.clone_ref(py));
            }
            // v3.1.2: Store FULL path for Differential Shadow Merging
            let mut full_map = self.full_path_map.lock().unwrap();
            full_map.insert(p.clone(), shadow.clone_ref(py));
        }

        
        Ok(shadow)
    }

    /// [v3.1 Zero Trust] Commit Delta Log to Pending State
    /// This applies the implicit mutations (captured in shadow objects) to the pending_data/heavy buffers.
    pub fn commit(&self, py: Python) -> PyResult<()> {
        let cache = self.shadow_cache.lock().unwrap();
        
        for (_, (original, shadow)) in cache.iter() {
            // If original IS shadow (re-shadow case), skip
            if original.bind(py).as_ptr() == shadow.bind(py).as_ptr() {
                 continue;
            }
            
            let orig_bind = original.bind(py);
            let _type_name = orig_bind.get_type().name()?.to_string();
            
            // Merge Shadow back to Original?
            // NO! We merge Shadow into PENDING buffers (which are copies of state).
            // Wait. `original` comes from `ctx.domain...`.
            // `ctx.domain` accesses `state` via `engine.state`.
            // `engine.state` is immutable.
            // So `original` IS likely inside `pending_data`? 
            // NO. `ctx` is created from `engine.state` (current version).
            // `pending_data` is EMPTY until we write to it.
            // If we mutate `ctx.domain.data['x']`, we are mutating the SHADOW of 'x'.
            // Unifying this with `pending_data` requires us to know WHERE `x` belongs in the state tree.
            // BUT `DeltaEntry` has `path`.
            // `shadow_cache` does NOT have path (it maps ID -> Shadow).
            
            // Re-evaluating Strategy:
            // `DeltaEntry` has `path`, `value`, `old_value`.
            // When `log_delta` is called (by Proxy), we record the CHANGE.
            // `DeltaEntry.value` IS the new value.
            // So iterating `delta_log` is enough to reconstruct `pending_data`?
            // YES!
            // `shadow_cache` ensures we are mutating a safe copy, but `delta_log` records exactly WHAT to apply.
            // `tx.update(py, data=...)` calls `pending_data.update(...)`.
            
            // So `commit` should iterate `delta_log` and apply changes to `pending_data`.
        }
        
        // Revised Commit Logic: Apply Delta Log
        let log = self.delta_log.lock().unwrap();
        for entry in log.iter() {
            // Entry has `path` (e.g. "domain.data.idiomatic").
            // We need to set this value in `self.pending_data`.
            // But `pending_data` is a flat dict? No, it's a structural dict mirroring state output.
            // Actually, `pending_data` accumulates updates.
            // We need to expand "domain.data.idiomatic" into nesting.
            // AND we need to handle "heavy" zone paths.
            
            if entry.op != "SET" { continue; }
            if let Some(ref new_val) = entry.value {
                 // Check Zone
                 let is_heavy = crate::zones::resolve_zone(&entry.path) == crate::zones::ContextZone::Heavy;
                 let target_dict = if is_heavy { &self.pending_heavy } else { &self.pending_data };
                 
                 // [v3.3 Fix] Heavy Zone Namespace Mapping
                 // state.heavy is a flat map {key: val}, but path is "heavy.key".
                 // We must strip the prefix to avoid nesting.
                 let final_path = if is_heavy {
                     entry.path.strip_prefix("heavy.").unwrap_or(&entry.path)
                 } else {
                     &entry.path
                 };

                 // Apply to target_dict at path
                 set_nested_value(py, target_dict, final_path, new_val)?;
            }
        }
        
        Ok(())
    }

    /// [v3.1 Zero Trust] Log operation for Audit
    #[pyo3(name = "log_delta", signature = (path, old_val=None, new_val=None))]
    pub fn log_delta(&self, py: Python, path: String, old_val: Option<PyObject>, new_val: Option<PyObject>) -> PyResult<()> {
        let entry = crate::delta::DeltaEntry {
            path: path.clone(),
            op: "SET".to_string(),
            value: new_val.as_ref().map(|v| v.clone_ref(py)),
            old_value: old_val.as_ref().map(|v| v.clone_ref(py)),
            target: None,
            key: None,
        };
        
        self.delta_log.lock().unwrap().push(entry);
        Ok(())
    }

    /// Internal: Log operation for Audit (Full)
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

    /// [INC-013] Helper: Check if object is a tracked Shadow.
    #[pyo3(name = "is_known_shadow")]
    pub fn is_known_shadow(&self, py: Python, obj: PyObject) -> bool {
        let ptr = obj.bind(py).as_ptr() as usize;
        let cache = self.shadow_cache.lock().unwrap();
        
        if let Some((_, shadow)) = cache.get(&ptr) {
             // If the pointer we queried matches the stored shadow pointer, it IS a shadow.
             return shadow.bind(py).as_ptr() as usize == ptr;
        }
        false
    }
}
