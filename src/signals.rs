use pyo3::prelude::*;
use tokio::sync::broadcast;
use std::sync::Arc;
use once_cell::sync::Lazy;
use tokio::runtime::Runtime;

// Global Tokio Runtime for background tasks/channels
static RUNTIME: Lazy<Runtime> = Lazy::new(|| {
    Runtime::new().expect("Failed to create Tokio Runtime")
});

#[pyclass(module = "theus_core")]
#[derive(Clone)]
pub struct SignalHub {
    tx: broadcast::Sender<String>,
}

impl Default for SignalHub {
    fn default() -> Self {
        Self::new()
    }
}

#[pymethods]
impl SignalHub {
    #[new]
    pub fn new() -> Self {
        let (tx, _rx) = broadcast::channel(100); // Default capacity
        SignalHub { tx }
    }

    pub fn publish(&self, msg: String) -> usize {
        // Send returns Result<usize, SendError>. 
        // SendError means no active receivers, which is fine (return 0).
        self.tx.send(msg).unwrap_or(0)
    }

    pub fn subscribe(&self) -> SignalReceiver {
        let rx = self.tx.subscribe();
        SignalReceiver { 
            rx: Arc::new(tokio::sync::Mutex::new(rx)) 
        }
    }
}

#[pyclass(module = "theus_core")]
pub struct SignalReceiver {
    // We need Arc<Mutex> because PyO3 classes must be Send/Sync (mostly) 
    // and we need mutable access to call recv().
    // tokio::sync::Mutex fits well with async, but here we block.
    rx: Arc<tokio::sync::Mutex<broadcast::Receiver<String>>>,
}

#[pymethods]
impl SignalReceiver {
    /// Blocking receive. intended to be called via asyncio.to_thread()
    fn recv(&self, py: Python<'_>) -> PyResult<String> {
        let rx_arc = self.rx.clone();
        
        // Release GIL to allow other Python tasks (like publisher) to run
        py.allow_threads(move || {
            // Enter Tokio Runtime context
            RUNTIME.block_on(async move {
                // println!("DEBUG: Waiting for lock");
                let mut rx = rx_arc.lock().await;
                // println!("DEBUG: Got lock, waiting for recv");
                match rx.recv().await {
                    Ok(msg) => {
                        // println!("DEBUG: Recv ok: {}", msg);
                        Ok(msg)
                    },
                    Err(broadcast::error::RecvError::Closed) => {
                        Err(pyo3::exceptions::PyStopAsyncIteration::new_err("Channel Closed"))
                    },
                    Err(broadcast::error::RecvError::Lagged(count)) => {
                        Err(pyo3::exceptions::PyRuntimeError::new_err(format!("Channel Lagged: missed {} messages", count)))
                    }
                }
            })
        })
    }
}
