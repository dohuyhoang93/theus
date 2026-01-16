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

/// Theus Core Rust Extension
#[pymodule]
fn theus_core(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core
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

    Ok(())
}
