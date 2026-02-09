use pyo3::prelude::*;

#[pyclass(module = "theus_core", eq, eq_int)]
#[derive(PartialEq, Clone, Debug)]
pub enum ContextZone {
    Data,
    Signal,
    Meta,
    Heavy,
    Log, // New Zone
}

pub const CAP_READ: u8   = 1 << 0; // 1
pub const CAP_APPEND: u8 = 1 << 1; // 2
pub const CAP_UPDATE: u8 = 1 << 2; // 4
pub const CAP_DELETE: u8 = 1 << 3; // 8
// pub const CAP_ADMIN: u8  = 1 << 4; // 16 (Bypass Physics) - Unused

pub fn resolve_zone(key: &str) -> ContextZone {
    // Structural Support: Check all segments
    let segments: Vec<&str> = key.split('.').collect();
    
    for segment in segments {
        if segment.starts_with("sig_") || segment.starts_with("cmd_") || segment == "sig" {
            return ContextZone::Signal;
        }
        if segment.starts_with("meta_") || segment == "meta" {
            return ContextZone::Meta;
        }
        if segment.starts_with("heavy_") || segment == "heavy" {
            return ContextZone::Heavy;
        }
        if segment.starts_with("log_") || segment.starts_with("audit_") || segment == "log" {
            return ContextZone::Log;
        }
    }
    
    ContextZone::Data
}

pub fn get_zone_physics(zone: &ContextZone) -> u8 {
    match zone {
        ContextZone::Data => CAP_READ | CAP_APPEND | CAP_UPDATE | CAP_DELETE,
        ContextZone::Signal => CAP_READ | CAP_APPEND, // River: Flow only
        ContextZone::Meta => CAP_READ | CAP_UPDATE,   // Config: Tune, don't delete
        ContextZone::Heavy => CAP_READ | CAP_UPDATE,  // Ref Swap only
        ContextZone::Log => CAP_READ | CAP_APPEND,    // History: Append only
    }
}
