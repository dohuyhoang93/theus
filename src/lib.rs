#![allow(deprecated)]
use pyo3::prelude::*;

mod engine;
mod structures;
mod config;
pub mod audit;
mod fsm;

mod guards;
mod tracked;
mod zones;
mod signals;
mod shm;
mod shm_registry;
mod conflict;

mod supervisor;
mod proxy;


/// Theus Core Rust Extension
#[pymodule]
fn theus_core(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // v3.1 Supervisor/Proxy
    supervisor::register(py, m)?;

    proxy::register(py, m)?;

    // Core Engine
    m.add_class::<engine::TheusEngine>()?;
    m.add_class::<engine::Transaction>()?;
    m.add_class::<engine::OutboxCollector>()?;
    m.add("WriteTimeoutError", py.get_type_bound::<engine::WriteTimeoutError>())?;
    
    // Workflow
    m.add_class::<fsm::WorkflowEngine>()?;
    m.add("FSMState", py.get_type_bound::<fsm::FSMState>())?;

    // Signals (v3.1)
    m.add_class::<signals::SignalHub>()?;
    m.add_class::<signals::SignalReceiver>()?;

    // Managed Memory (v3.2)
    // Managed Memory (v3.2) - Moved to shm submodule
    // m.add_class::<shm_registry::MemoryRegistry>()?;
    
    // Structures
    m.add_class::<structures::State>()?;
    m.add_class::<structures::ProcessContext>()?;
    m.add_class::<structures::FrozenDict>()?;
    m.add_class::<structures::OutboxMsg>()?;
    m.add_class::<structures::MetaLogEntry>()?;
    m.add("ContextError", py.get_type_bound::<structures::ContextError>())?;
    
    // Guards
    m.add_class::<guards::ContextGuard>()?;
    
    // Config
    m.add_class::<config::ConfigLoader>()?;
    m.add("SchemaViolationError", py.get_type_bound::<config::SchemaViolationError>())?;
    
    // Audit
    m.add_class::<audit::AuditSystem>()?;
    m.add_class::<audit::AuditRecipe>()?;
    m.add_class::<audit::AuditLevel>()?;
    m.add_class::<audit::AuditLogEntry>()?;
    m.add("AuditBlockError", py.get_type_bound::<audit::AuditBlockError>())?;
    m.add("AuditAbortError", py.get_type_bound::<audit::AuditAbortError>())?;
    m.add("AuditStopError", py.get_type_bound::<audit::AuditStopError>())?;
    m.add("AuditWarning", py.get_type_bound::<audit::AuditWarning>())?;
    
    // Conflict (v3.3)
    m.add_class::<conflict::ConflictManager>()?;
    m.add_class::<conflict::RetryDecision>()?;


    // Sub-module for SHM (v3.1)
    let shm_mod = PyModule::new_bound(py, "shm")?;
    shm::theus_shm(py, &shm_mod)?;
    shm_mod.add_class::<shm_registry::MemoryRegistry>()?;
    m.add_submodule(&shm_mod)?;

    Ok(())
}
