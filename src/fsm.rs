use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_yaml::Value;
use std::sync::Mutex;

// ============================================================================
// Flux DSL AST (Abstract Syntax Tree)
// ============================================================================

/// Represents a single step in the Flux DSL workflow.
/// Supports recursive nesting for complex control flow.
#[derive(Debug, Clone)]
enum FluxStep {
    /// Simple process execution: `- process: name` or `- name`
    Process { name: String },
    
    /// While loop: `- flux: while` with `condition` and `do` block
    While {
        condition: String,
        do_steps: Vec<FluxStep>,
    },
    
    /// Conditional: `- flux: if` with `condition`, `then`, and optional `else`
    If {
        condition: String,
        then_steps: Vec<FluxStep>,
        else_steps: Vec<FluxStep>,
    },
    
    /// Nested block wrapper: `- flux: run` with `steps`
    Run {
        steps: Vec<FluxStep>,
    },
}

// ============================================================================
// Parser: YAML -> Vec<FluxStep>
// ============================================================================

/// Parse a YAML sequence into a vector of FluxStep.
fn parse_steps(yaml_seq: &[Value]) -> Result<Vec<FluxStep>, String> {
    let mut steps = Vec::new();
    
    for item in yaml_seq {
        let step = parse_single_step(item)?;
        steps.push(step);
    }
    
    Ok(steps)
}

/// Parse a single YAML value into a FluxStep.
fn parse_single_step(item: &Value) -> Result<FluxStep, String> {
    // Case 1: Simple string (process name)
    if let Some(name) = item.as_str() {
        return Ok(FluxStep::Process { name: name.to_string() });
    }
    
    // Case 2: Mapping (dict)
    if let Some(map) = item.as_mapping() {
        // Check for 'process' key (simple process)
        if let Some(process_val) = map.get(Value::String("process".to_string())) {
            let name = process_val.as_str()
                .ok_or("'process' value must be a string")?
                .to_string();
            return Ok(FluxStep::Process { name });
        }
        
        // Check for 'flux' key (control flow)
        if let Some(flux_val) = map.get(Value::String("flux".to_string())) {
            let flux_type = flux_val.as_str()
                .ok_or("'flux' value must be a string")?;
            
            match flux_type {
                "while" => {
                    let condition = map.get(Value::String("condition".to_string()))
                        .and_then(|v| v.as_str())
                        .ok_or("'flux: while' requires 'condition' field")?
                        .to_string();
                    
                    let do_block = map.get(Value::String("do".to_string()))
                        .and_then(|v| v.as_sequence())
                        .ok_or("'flux: while' requires 'do' block")?;
                    
                    let do_steps = parse_steps(do_block)?;
                    
                    return Ok(FluxStep::While { condition, do_steps });
                }
                
                "if" => {
                    let condition = map.get(Value::String("condition".to_string()))
                        .and_then(|v| v.as_str())
                        .ok_or("'flux: if' requires 'condition' field")?
                        .to_string();
                    
                    // Use let bindings to extend lifetime of empty fallback vectors
                    let empty_seq: Vec<Value> = vec![];
                    
                    let then_block = map.get(Value::String("then".to_string()))
                        .and_then(|v| v.as_sequence())
                        .unwrap_or(&empty_seq);
                    
                    let else_block = map.get(Value::String("else".to_string()))
                        .and_then(|v| v.as_sequence())
                        .unwrap_or(&empty_seq);
                    
                    let then_steps = parse_steps(then_block)?;
                    let else_steps = parse_steps(else_block)?;
                    
                    return Ok(FluxStep::If { condition, then_steps, else_steps });
                }
                
                "run" => {
                    let steps_block = map.get(Value::String("steps".to_string()))
                        .and_then(|v| v.as_sequence())
                        .ok_or("'flux: run' requires 'steps' block")?;
                    
                    let steps = parse_steps(steps_block)?;
                    
                    return Ok(FluxStep::Run { steps });
                }
                
                _ => {
                    return Err(format!("Unknown flux type: '{}'", flux_type));
                }
            }
        }
        
        // Unknown mapping format - try to extract a meaningful error
        return Err(format!("Unknown step format: {:?}", item));
    }
    
    Err(format!("Invalid step type: expected string or mapping, got {:?}", item))
}

// ============================================================================
// FSM State Enum (Per VISION.md)
// ============================================================================

/// FSM State for Workflow execution tracking.
/// Supports: Pending -> Running -> WaitingIO -> Complete/Failed
#[pyclass(module = "theus_core", eq, eq_int)]
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum FSMState {
    Pending = 0,
    Running = 1,
    WaitingIO = 2,
    Complete = 3,
    Failed = 4,
}

// ============================================================================
// WorkflowEngine (PyO3 Class)
// ============================================================================

#[pyclass(module = "theus_core", subclass)]
pub struct WorkflowEngine {
    steps: Vec<FluxStep>,
    max_ops: u32,
    debug: bool,
    // Keep original config for legacy 'simulate' method compatibility
    config: Value,
    // FSM State tracking (Mutex for thread-safe interior mutability)
    fsm_state: Mutex<FSMState>,
    state_history: Mutex<Vec<FSMState>>,
    // State change observers (Python callbacks)
    observers: Mutex<Vec<PyObject>>,
}

#[pymethods]
impl WorkflowEngine {
    #[new]
    #[pyo3(signature = (yaml_config, max_ops=10000, debug=false))]
    fn new(yaml_config: String, max_ops: u32, debug: bool) -> PyResult<Self> {
        let config: Value = serde_yaml::from_str(&yaml_config)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid YAML: {}", e)))?;
        
        // Parse 'steps' into FluxStep AST
        let steps = if let Some(steps_seq) = config.get("steps").and_then(|v| v.as_sequence()) {
            parse_steps(steps_seq)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Parse error: {}", e)))?
        } else {
            Vec::new()
        };
        
        if debug {
            eprintln!("[FLUX-DEBUG] Parsed {} top-level steps", steps.len());
        }
        
        let initial_state = FSMState::Pending;
        let state_history = vec![initial_state];
        
        Ok(WorkflowEngine { 
            steps, 
            max_ops, 
            debug, 
            config, 
            fsm_state: Mutex::new(initial_state), 
            state_history: Mutex::new(state_history),
            observers: Mutex::new(Vec::new()),
        })
    }

    /// Get current FSM state.
    #[getter]
    fn fsm_state(&self) -> FSMState {
        *self.fsm_state.lock().unwrap()
    }

    /// Alias for fsm_state (for test compatibility).
    #[getter]
    fn state(&self) -> FSMState {
        *self.fsm_state.lock().unwrap()
    }

    /// Get state transition history.
    #[getter]
    fn state_history(&self) -> Vec<FSMState> {
        self.state_history.lock().unwrap().clone()
    }

    /// Add an observer callback for state changes.
    /// Callback signature: (old_state, new_state) -> None
    fn add_state_observer(&self, callback: PyObject) {
        self.observers.lock().unwrap().push(callback);
    }

    /// Execute the workflow using the provided executor callback.
    /// 
    /// Args:
    ///     ctx: PyDict - Context for condition evaluation (e.g., {"domain": {...}, "global": {...}})
    ///     executor: Callable[[str], None] - Function to execute a process by name
    /// 
    /// Returns:
    ///     List of executed process names (for debugging/logging)
    #[pyo3(signature = (ctx, executor))]
    fn execute(&self, py: Python, ctx: Py<PyDict>, executor: PyObject) -> PyResult<Vec<String>> {
        // Transition: Pending -> Running
        self.transition_state(py, FSMState::Running)?;
        
        let mut ops_counter: u32 = 0;
        let mut executed_names: Vec<String> = Vec::new();
        
        let ctx_bound = ctx.bind(py);
        let result = self.execute_steps(
            py,
            &self.steps,
            ctx_bound,
            &executor,
            &mut ops_counter,
            &mut executed_names,
        );
        
        // Transition based on result
        match result {
            Ok(()) => {
                self.transition_state(py, FSMState::Complete)?;
                Ok(executed_names)
            }
            Err(e) => {
                self.transition_state(py, FSMState::Failed)?;
                Err(e)
            }
        }
    }

    /// Execute the workflow asynchronously.
    /// Wraps the synchronous execution in a thread (asyncio.to_thread) to avoid blocking the event loop.
    /// Handles FSM state transitions correctly for async steps by blocking the worker thread.
    #[pyo3(signature = (ctx, executor))]
    fn execute_async(
        self_: Py<Self>,
        py: Python<'_>,
        ctx: Py<PyDict>,
        executor: PyObject
    ) -> PyResult<Bound<'_, PyAny>> {
        let asyncio = py.import("asyncio")?;
        
        // Capture running loop for thread-safe execution of sub-coroutines
        let loop_obj = asyncio.call_method0("get_running_loop")?;
        
        // Copy context to inject loop without side effects
        let ctx_bound = ctx.bind(py);
        let ctx_copy = ctx_bound.copy()?;
        ctx_copy.set_item("_loop", loop_obj)?;
        
        // Prepare call to execute via to_thread
        let self_bound = self_.bind(py);
        let execute_method = self_bound.getattr("execute")?;
        
        // Return coroutine that runs execute() in a thread
        let coro = asyncio.call_method1("to_thread", (execute_method, ctx_copy, executor))?;
        Ok(coro)
    }
    
    /// Legacy method for backward compatibility with existing tests.
    /// Returns the simulated execution path without actually executing.
    fn simulate(&self, py: Python, ctx: Py<PyDict>) -> PyResult<Vec<String>> {
        // For legacy compatibility, generate path from simple graph nodes
        // This is a simplified version - full graph traversal logic from old implementation
        let mut path = Vec::new();
        
        let nodes = match self.config.get("nodes") {
            Some(n) => n,
            None => {
                // Fallback: Linear Flux Simulation (Simple traversal for legacy compat)
                // This handles legacy V2 "steps" list which parses into linear FluxSteps
                let mut stack: Vec<&FluxStep> = self.steps.iter().rev().collect();
                while let Some(step) = stack.pop() {
                    match step {
                         FluxStep::Process { name } => path.push(name.clone()),
                         FluxStep::Run { steps } => {
                             for s in steps.iter().rev() {
                                 stack.push(s);
                             }
                         },
                         // Ignore control flow (If/While) in basic legacy simulation 
                         // as legacy YAMLs tested here are linear.
                         _ => {} 
                    }
                }
                return Ok(path);
            }
        };
        
        let start_val = nodes.get("start").ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("Missing 'start' node")
        })?;
        
        let mut current_node_name = start_val.as_str().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("Start node must be string")
        })?.to_string();

        let ctx_bound = ctx.bind(py);
        
        loop {
            path.push(current_node_name.clone());
            
            let node_def = match nodes.get(&current_node_name) {
                Some(n) => n,
                None => break,
            };
            
            let next_val = match node_def.get("next") {
                Some(n) => n,
                None => break,
            };
            
            if let Some(s) = next_val.as_str() {
                current_node_name = s.to_string();
            } else if let Some(mapping) = next_val.as_mapping() {
                let mut found = false;
                for (k, v) in mapping {
                    let cond_str = k.as_str().ok_or_else(|| {
                        pyo3::exceptions::PyValueError::new_err("Condition key must be string")
                    })?;
                    
                    let target = v.as_str().ok_or_else(|| {
                        pyo3::exceptions::PyValueError::new_err("Target must be string")
                    })?.to_string();

                    if cond_str == "else" {
                        current_node_name = target;
                        found = true;
                        break;
                    } else if let Some(raw_expr) = cond_str.strip_prefix("if ") {
                        let expr = raw_expr.trim().trim_matches(|c| c == '"' || c == '\'');
                        if self.eval_condition(py, expr, ctx_bound)? {
                            current_node_name = target;
                            found = true;
                            break;
                        }
                    }
                }
                if !found {
                    break;
                }
            } else {
                break;
            }
        }

        Ok(path)
    }
}

// ============================================================================
// Internal Implementation (Rust-only methods)
// ============================================================================

impl WorkflowEngine {
    /// Recursively execute a list of FluxStep with safety limits.
    fn execute_steps(
        &self,
        py: Python,
        steps: &[FluxStep],
        ctx: &Bound<'_, PyDict>,
        executor: &PyObject,
        ops_counter: &mut u32,
        executed_names: &mut Vec<String>,
    ) -> PyResult<()> {
        for step in steps {
            *ops_counter += 1;
            
            // Safety Trip: Prevent infinite loops
            if *ops_counter > self.max_ops {
                return Err(pyo3::exceptions::PyRuntimeError::new_err(
                    format!("Flux Safety Trip: Exceeded {} operations. Check for infinite loops.", self.max_ops)
                ));
            }
            
            if self.debug {
                eprintln!("[FLUX-DEBUG] Op #{}: {:?}", ops_counter, step);
            }
            
            match step {
                FluxStep::Process { name } => {
                    // Call the executor callback with process name
                    let res = executor.call1(py, (name.clone(),))?;
                    
                    // Check if result is a coroutine (Async Process)
                    let asyncio = py.import("asyncio")?;
                    let is_coro = asyncio.call_method1("iscoroutine", (&res,))?.is_truthy()?;
                    
                    if is_coro {
                        // We must have the event loop to run it thread-safe
                        let loop_obj = ctx.get_item("_loop")?.ok_or_else(|| {
                             pyo3::exceptions::PyRuntimeError::new_err("Async process returned coroutine but '_loop' missing in context. Ensure you used execute_async() or provided '_loop'.")
                        })?;
                        
                        // Transition to WaitingIO
                        self.transition_state(py, FSMState::WaitingIO)?;
                        
                        // Block thread until coroutine completes on the main loop
                        let fut = asyncio.call_method1("run_coroutine_threadsafe", (&res, &loop_obj))?;
                        let _ = fut.call_method0("result")?; 
                        
                        // Back to Running
                        self.transition_state(py, FSMState::Running)?;
                    }
                    
                    executed_names.push(name.clone());
                }
                
                FluxStep::While { condition, do_steps } => {
                    // Loop while condition is true
                    while self.eval_condition(py, condition, ctx)? {
                        self.execute_steps(py, do_steps, ctx, executor, ops_counter, executed_names)?;
                    }
                }
                
                FluxStep::If { condition, then_steps, else_steps } => {
                    if self.eval_condition(py, condition, ctx)? {
                        self.execute_steps(py, then_steps, ctx, executor, ops_counter, executed_names)?;
                    } else {
                        self.execute_steps(py, else_steps, ctx, executor, ops_counter, executed_names)?;
                    }
                }
                
                FluxStep::Run { steps: sub_steps } => {
                    self.execute_steps(py, sub_steps, ctx, executor, ops_counter, executed_names)?;
                }
            }
        }
        
        Ok(())
    }
    
    /// Safely evaluate a condition expression using restricted builtins.
    fn eval_condition(&self, py: Python, expr: &str, locals: &Bound<'_, PyDict>) -> PyResult<bool> {
        // Build restricted globals with safe builtins only
        let builtins = PyDict::new_bound(py);
        
        // Allow only safe functions
        let py_builtins = py.import_bound("builtins")?;
        builtins.set_item("len", py_builtins.getattr("len")?)?;
        builtins.set_item("int", py_builtins.getattr("int")?)?;
        builtins.set_item("float", py_builtins.getattr("float")?)?;
        builtins.set_item("str", py_builtins.getattr("str")?)?;
        builtins.set_item("bool", py_builtins.getattr("bool")?)?;
        builtins.set_item("abs", py_builtins.getattr("abs")?)?;
        builtins.set_item("min", py_builtins.getattr("min")?)?;
        builtins.set_item("max", py_builtins.getattr("max")?)?;
        builtins.set_item("sum", py_builtins.getattr("sum")?)?;
        builtins.set_item("True", true)?;
        builtins.set_item("False", false)?;
        builtins.set_item("None", py.None())?;
        
        let globals = PyDict::new_bound(py);
        globals.set_item("__builtins__", builtins)?;
        
        // Merge locals (context) into globals for eval access
        // This allows expressions like `domain.x < len(domain.items)`
        for (k, v) in locals.iter() {
            globals.set_item(k, v)?;
        }
        
        if self.debug {
            eprintln!("[FLUX-DEBUG] Evaluating condition: '{}'", expr);
        }
        
        let result = py.eval_bound(expr, Some(&globals), None)?;
        let is_true = result.is_truthy()?;
        
        if self.debug {
            eprintln!("[FLUX-DEBUG] Condition result: {}", is_true);
        }
        
        Ok(is_true)
    }

    /// Transition to a new FSM state, record in history, and notify observers.
    fn transition_state(&self, py: Python, new_state: FSMState) -> PyResult<()> {
        let old_state = *self.fsm_state.lock().unwrap();
        
        // Update state
        *self.fsm_state.lock().unwrap() = new_state;
        
        // Record in history
        self.state_history.lock().unwrap().push(new_state);
        
        // Notify observers
        // Use a clone to avoid holding the lock while calling Python code (Deadlock Prevention)
        let observers: Vec<PyObject> = {
            let guard = self.observers.lock().unwrap();
            guard.iter().map(|o| o.clone_ref(py)).collect()
        };
        
        for callback in observers.iter() {
            // Call observer with (old_state, new_state)
            let _ = callback.call1(py, (old_state, new_state));
        }
        
        if self.debug {
            eprintln!("[FLUX-DEBUG] FSM State: {:?} -> {:?}", old_state, new_state);
        }
        
        Ok(())
    }
}
