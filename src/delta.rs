use pyo3::prelude::*;
use std::sync::{Mutex, OnceLock};
use std::collections::HashSet;

static LOGGED_HEAVY_PATHS: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();


#[derive(Debug)]
pub struct DeltaEntry {
    pub path: String,
    pub op: String,
    pub value: Option<PyObject>,
    pub old_value: Option<PyObject>,
    pub target: Option<PyObject>,
    pub key: Option<String>,
}

#[pyclass]
pub struct Transaction {
    pub log: Vec<DeltaEntry>,
    shadow_cache: std::collections::HashMap<usize, (PyObject, PyObject)>, // id -> (original, shadow)
}

impl Transaction {
    pub(crate) fn log_internal(
        &mut self, 
        path: String, 
        op: String, 
        value: Option<PyObject>, 
        old_value: Option<PyObject>, 
        target: Option<PyObject>, 
        key: Option<String>
    ) {
        self.log.push(DeltaEntry {
            path, op, value, old_value, target, key 
        });
    }
}

impl Default for Transaction {
    fn default() -> Self {
        Self::new()
    }
}

#[pymethods]
impl Transaction {
    #[new]
    pub fn new() -> Self {
        Transaction { 
            log: Vec::new(),
            shadow_cache: std::collections::HashMap::new(),
        }
    }

    #[pyo3(signature = (path, op, value=None, old_value=None, target=None, key=None))]
    #[pyo3(name = "log")]
    fn log_py(
        &mut self, 
        path: String, 
        op: String, 
        value: Option<PyObject>, 
        old_value: Option<PyObject>, 
        target: Option<PyObject>, 
        key: Option<String>
    ) {
        self.log_internal(path, op, value, old_value, target, key);
    }
    
    #[pyo3(signature = (original, path=None))]
    pub fn get_shadow(&mut self, py: Python, original: PyObject, path: Option<String>) -> PyResult<PyObject> {
        let id = original.bind(py).as_ptr() as usize;
        
        if let Some((_, shadow)) = self.shadow_cache.get(&id) {
             return Ok(shadow.clone_ref(py));
        }
        
        // HEAVY Zone Check: Skip copy for heavy_ prefixed objects
        // NOTE: This is explicit, not silent - user must declare heavy_ prefix
        if let Some(ref p) = path {
            let leaf = p.split('.').next_back().unwrap_or(p);
            if crate::zones::resolve_zone(leaf) == crate::zones::ContextZone::Heavy {
                // Log explicitly that we're skipping copy for HEAVY zone (ONCE per path)
                let set_mutex = LOGGED_HEAVY_PATHS.get_or_init(|| Mutex::new(HashSet::new()));
                if let Ok(mut set) = set_mutex.lock() {
                    if !set.contains(p) {
                         eprintln!("[Theus] HEAVY zone: skipping shadow copy for '{}' (Logged once)", p);
                         set.insert(p.to_string());
                    }
                }
                
                self.shadow_cache.insert(id, (original.clone_ref(py), original.clone_ref(py)));
                return Ok(original);
            }
        }
        
        // Create Shadow with fallback for non-copyable types
        let copy_mod = PyModule::import(py, "copy")?;
        let shadow = match copy_mod.call_method1("copy", (&original,)) {
            Ok(s) => s.unbind(),
            Err(e) => {
                // NOTE: Log warning when fallback happens - behavior should not be silent
                let type_name = original.bind(py).get_type().name().ok().map(|n| n.to_string()).unwrap_or_else(|| "unknown".to_string());
                let path_str = path.as_deref().unwrap_or("unknown");
                eprintln!("[Theus] WARNING: Cannot copy '{}' (type: {}): {}. Using reference instead.", 
                         path_str, type_name, e);
                self.shadow_cache.insert(id, (original.clone_ref(py), original.clone_ref(py)));
                return Ok(original);
            }
        };
        
        // Disable Legacy Lock Manager on Shadow to prevent double-locking
        // This allows ContextGuard to manage writes freely on the shadow.
        // Writes to _ attributes are always allowed by LockedContextMixin.
        let _ = shadow.bind(py).setattr("_lock_manager", py.None());

        let shadow_id = shadow.bind(py).as_ptr() as usize;
        
        // Track
        self.shadow_cache.insert(id, (original.clone_ref(py), shadow.clone_ref(py)));
        // Also map shadow id to itself to prevent re-shadowing a shadow
        self.shadow_cache.insert(shadow_id, (original, shadow.clone_ref(py)));
        
        Ok(shadow)
    }
    
    pub fn commit(&mut self, py: Python) -> PyResult<()> {
        for (_, (original, shadow)) in self.shadow_cache.iter() {
            // If original IS shadow (re-shadow case), skip
            if original.bind(py).as_ptr() == shadow.bind(py).as_ptr() {
                 continue;
            }
            
            let orig_bind = original.bind(py);
            let type_name = orig_bind.get_type().name()?.to_string();
            
            if type_name == "list" {
                 // Simplest: original[:] = shadow -> original.__setitem__(slice(None), shadow)
                 let builtins = PyModule::import(py, "builtins")?;
                 let slice_cls = builtins.getattr("slice")?;
                 let slice = slice_cls.call1((py.None(),))?;
                 orig_bind.set_item(slice, shadow)?;
            } else if type_name == "dict" {
                 // original.clear(); original.update(shadow)
                 orig_bind.call_method0("clear")?;
                 orig_bind.call_method1("update", (shadow,))?;
            } else {
                 // Generic object: original.__dict__.update(shadow.__dict__)
                 if let Ok(orig_dict) = orig_bind.getattr("__dict__") {
                      if let Ok(shadow_dict) = shadow.bind(py).getattr("__dict__") {
                           orig_dict.call_method1("update", (shadow_dict,))?;
                      }
                 }
            }
        }
        Ok(())
    }

    pub fn rollback(&mut self, py: Python) -> PyResult<()> {
        for entry in self.log.iter().rev() {
             if let (Some(target), Some(key), Some(old)) = (&entry.target, &entry.key, &entry.old_value) {
                 if entry.op == "SET" {
                     target.bind(py).setattr(key.as_str(), old)?;
                 }
             }
        }
        self.log.clear();
        self.shadow_cache.clear();
        Ok(())
    }
}
