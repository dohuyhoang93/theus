use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs::{OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::collections::HashMap;
use std::path::Path;
use sysinfo::{Pid, System};
use shared_memory::ShmemConf;
use std::sync::{Arc, Mutex};

const REGISTRY_FILE: &str = ".theus_memory_registry.jsonl";

#[derive(Serialize, Deserialize, Debug, Clone)]
struct AllocRecord {
    name: String,
    pid: u32,
    session: String,
    size: usize,
    ts: f64,
}

#[pyclass]
pub struct MemoryRegistry {
    session_id: String,
    // pid field removed, use dynamic std::process::id()
    owned_allocations: Arc<Mutex<HashMap<String, usize>>>, // name -> size
}

#[pymethods]
impl MemoryRegistry {
    #[new]
    fn new(session_id: String) -> Self {
        let registry = MemoryRegistry {
            session_id,
            owned_allocations: Arc::new(Mutex::new(HashMap::new())),
        };
        
        // Auto-scan on startup
        registry.scan_zombies();
        registry
    }

    pub fn scan_zombies(&self) {
        if !Path::new(REGISTRY_FILE).exists() {
            return;
        }

        let mut sys = System::new_all();
        sys.refresh_all();
        
        let path = Path::new(REGISTRY_FILE);
        let file = match std::fs::File::open(path) {
            Ok(f) => f,
            Err(_) => return,
        };
        let reader = BufReader::new(file);

        let mut active_records = Vec::new();
        let mut _zombies_cleaned = 0;
        let mut records_dropped = 0;
        let mut lines_read = 0;

        for l in reader.lines().map_while(Result::ok) {
            lines_read += 1;
            if let Ok(record) = serde_json::from_str::<AllocRecord>(&l) {
                // Check Liveness
                let current_pid = std::process::id();
                let is_alive = if record.pid == current_pid {
                    true
                } else {
                    let alive = sys.process(Pid::from_u32(record.pid)).is_some();
                    if alive && record.pid == 99999999 {
                         println!("[TheusCore] WARNING: PID 99999999 is ALIVE according to sysinfo!");
                    }
                    alive
                };

                if !is_alive {
                    // ZOMBIE! Unlink via open-then-drop with owner=true
                    // Even if Open fails (already gone), we drop the record.
                    if let Ok(mut shm) = ShmemConf::new().os_id(&record.name).open() {
                        shm.set_owner(true);
                        _zombies_cleaned += 1;
                    }
                    records_dropped += 1;
                } else {
                    active_records.push(record);
                }
            }
        }

        if records_dropped > 0 || active_records.len() < lines_read {
            eprintln!("[TheusCore] Registry GC: {} lines read, {} kept ({} dropped). Rewriting...", lines_read, active_records.len(), records_dropped);
            match std::fs::File::create(REGISTRY_FILE) {
                Ok(mut f) => {
                    for rec in active_records {
                        if let Ok(s) = serde_json::to_string(&rec) {
                            let _ = writeln!(f, "{}", s);
                        }
                    }
                    eprintln!("[TheusCore] Cleanup SUCCESS. File rewritten.");
                }
                Err(e) => {
                    eprintln!("[TheusCore] Cleanup ERROR: Failed to create reg file: {}", e);
                }
            }
        } else {
             eprintln!("[TheusCore] Registry GC: No cleanup needed. All records alive?");
        }
    }

    pub fn log_allocation(&self, name: String, size: usize) {
        let record = AllocRecord {
            name: name.clone(),
            pid: std::process::id(), // Dynamic PID
            session: self.session_id.clone(),
            size,
            ts: 0.0, // Timestamp not critical for now
        };
        
        // Track locally
        if let Ok(mut map) = self.owned_allocations.lock() {
            map.insert(name, size);
        }

        // Append to file
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(REGISTRY_FILE)
            .unwrap_or_else(|_| std::fs::File::create(REGISTRY_FILE).unwrap());
            
        if let Ok(s) = serde_json::to_string(&record) {
            let _ = writeln!(file, "{}", s);
        }
    }
    
    pub fn cleanup(&self) {
        // Unlink all owned
        if let Ok(map) = self.owned_allocations.lock() {
             for (name, _) in map.iter() {
                 // Open and Unlink
                 if let Ok(mut shm) = ShmemConf::new().os_id(name).open() {
                     shm.set_owner(true);
                     // Drop -> Unlink
                 }
             }
        }
    }
}
