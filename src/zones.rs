use once_cell::sync::Lazy;
use std::collections::HashMap;
use std::sync::Mutex;
use pyo3::prelude::*;

static PHYSICS_OVERRIDES: Lazy<Mutex<HashMap<String, u8>>> = Lazy::new(|| Mutex::new(HashMap::new()));

#[pyfunction]
pub fn register_physics_override(path: String, caps: u8) {
    if let Ok(mut map) = PHYSICS_OVERRIDES.lock() {
        map.insert(path, caps);
    }
}

#[pyfunction]
pub fn clear_physics_overrides() {
    if let Ok(mut map) = PHYSICS_OVERRIDES.lock() {
        map.clear();
    }
}

pub fn get_physics_override(path: &str) -> Option<u8> {
    if let Ok(map) = PHYSICS_OVERRIDES.lock() {
        // [RFC-001] Check exact match first
        if let Some(&caps) = map.get(path) {
            return Some(caps);
        }
        
        // Structural Support: Check prefixes (e.g. domain.const_data overrides domain.const_data[key])
        let normalized = path.replace("[", ".").replace("]", "");
        let mut segments: Vec<&str> = normalized.split('.').collect();
        
        while !segments.is_empty() {
            let prefix = segments.join(".");
            if let Some(&caps) = map.get(&prefix) {
                return Some(caps);
            }
            segments.pop();
        }
        
        None
    } else {
        None
    }
}

#[pyclass(module = "theus_core", eq, eq_int)]
#[derive(PartialEq, Clone, Debug)]
pub enum ContextZone {
    Data,
    Signal,
    Meta,
    Heavy,
    Log,
    // [RFC-001 §5] CONSTANT: Read-Only forever. No Admin override.
    Constant,
    // [RFC-001 Handbook §1.1] PRIVATE: Hidden from non-admin processes.
    Private,
}

pub const CAP_READ: u8   = 1 << 0; // 1
pub const CAP_APPEND: u8 = 1 << 1; // 2
pub const CAP_UPDATE: u8 = 1 << 2; // 4
pub const CAP_DELETE: u8 = 1 << 3; // 8
pub const CAP_NONE: u8   = 0;      // 0 - Completely private

pub fn resolve_zone(key: &str) -> ContextZone {
    // Structural Support: Check all segments (handle both dot and bracket notation)
    let normalized = key.replace("[", ".").replace("]", "");
    let segments: Vec<&str> = normalized.split('.').collect();
    
    for segment in segments {
        // [RFC-001 §5] CONSTANT zone — no mutation ever, even Admin bypass
        if segment.starts_with("const_") {
            return ContextZone::Constant;
        }
        // [RFC-001 Handbook §1.1] PRIVATE zone — hidden from Observer processes
        if segment.starts_with("internal_") {
            return ContextZone::Private;
        }
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
        ContextZone::Data     => CAP_READ | CAP_APPEND | CAP_UPDATE | CAP_DELETE,
        ContextZone::Signal   => CAP_READ | CAP_APPEND, // River: Flow only
        ContextZone::Meta     => CAP_READ | CAP_UPDATE, // Config: Tune, don't delete
        ContextZone::Heavy    => CAP_READ | CAP_UPDATE, // Ref Swap only
        ContextZone::Log      => CAP_READ | CAP_APPEND, // History: Append only
        // [RFC-001 §5] CONSTANT: Read ceiling = READ only. Can NEVER be elevated.
        ContextZone::Constant => CAP_READ,
        // [RFC-001 Handbook §1.1] PRIVATE: No capability for public processes.
        ContextZone::Private  => CAP_NONE,
    }
}

/// [RFC-001 §5] Returns true if this zone is UNBREAKABLE (Admin cannot override).
/// Constant fields cannot be mutated by any process, including admin transactions.
pub fn is_absolute_ceiling(zone: &ContextZone) -> bool {
    matches!(zone, ContextZone::Constant)
}
