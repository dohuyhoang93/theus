use pyo3::prelude::*;

#[pyclass(module = "theus_core", eq, eq_int)]
#[derive(PartialEq, Clone, Debug)]
pub enum ContextZone {
    Data,
    Signal,
    Meta,
    Heavy,
}

pub fn resolve_zone(key: &str) -> ContextZone {
    if key.starts_with("sig_") || key.starts_with("cmd_") {
        return ContextZone::Signal;
    }
    if key.starts_with("meta_") {
        return ContextZone::Meta;
    }
    if key.starts_with("heavy_") {
        return ContextZone::Heavy;
    }
    ContextZone::Data
}
