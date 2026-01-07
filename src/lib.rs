#![allow(deprecated)]
use pyo3::prelude::*;

mod delta;
mod audit;
mod engine;
mod guards;
mod zones;
mod structures;
mod registry;
mod fsm;

/// Theus Core Rust Extension
#[pymodule]
fn theus_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<engine::Engine>()?;
    m.add_class::<delta::Transaction>()?;
    m.add_class::<guards::ContextGuard>()?; 
    m.add_class::<zones::ContextZone>()?;
    m.add_class::<structures::TrackedList>()?;
    m.add_class::<structures::TrackedDict>()?;
    m.add_class::<structures::FrozenList>()?;
    m.add_class::<structures::FrozenDict>()?;
    m.add_class::<fsm::StateMachine>()?;
    Ok(())
}
