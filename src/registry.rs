use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use pyo3::prelude::*;

// Thread-safe global registry
// Stores process_name -> Python Function
static PROCESS_REGISTRY: OnceLock<Mutex<HashMap<String, PyObject>>> = OnceLock::new();

fn get_registry() -> &'static Mutex<HashMap<String, PyObject>> {
    PROCESS_REGISTRY.get_or_init(|| Mutex::new(HashMap::new()))
}

pub fn register_process(name: String, process: PyObject) {
    let mut registry = get_registry().lock().unwrap();
    registry.insert(name, process);
}

pub fn get_process(py: Python, name: &str) -> Option<PyObject> {
    let registry = get_registry().lock().unwrap();
    registry.get(name).map(|obj| obj.clone_ref(py))
}
