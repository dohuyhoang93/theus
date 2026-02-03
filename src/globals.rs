use std::sync::{Arc, Mutex};
use std::sync::OnceLock;
use crate::audit::RingBuffer;

/// Process-Global Audit Buffer
/// Shared across ALL Sub-interpreters.
/// OnceLock ensures it is only initialized once per PROCESS, not per Interpreter.
pub static GLOBAL_AUDIT_BUFFER: OnceLock<Arc<Mutex<RingBuffer>>> = OnceLock::new();
