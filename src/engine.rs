use pyo3::prelude::*;
// use std::collections::HashMap; // Moved to registry
// use std::sync::{Arc, Mutex}; // Moved to registry
use crate::audit::AuditPolicy;
use crate::guards::ContextGuard;
use crate::delta::Transaction;
use crate::registry;
use pyo3::types::PyAnyMethods;

#[pyclass(subclass)]
pub struct Engine {
    ctx: PyObject, 
    // process_registry: HashMap<String, PyObject>, // Moved to global registry
    audit_policy: Option<AuditPolicy>,
    strict_mode: bool,
}

impl Engine {
    fn raise_audit_error(py: Python, err: crate::audit::AuditError) -> PyResult<PyObject> {
        let audit_mod = PyModule::import(py, "theus.audit")?;
        
        match err {
            crate::audit::AuditError::Block(msg) => {
                 let exc = audit_mod.getattr("AuditBlockError")?;
                 Err(PyErr::from_value(exc.call1((msg,))?))
            },
            crate::audit::AuditError::Interlock(msg) => {
                 let exc = audit_mod.getattr("AuditInterlockError")?;
                 Err(PyErr::from_value(exc.call1((msg,))?))
            }
        }
    }
}

#[pymethods]
impl Engine {
    #[new]
    #[pyo3(signature = (ctx, strict_mode=None, audit_recipe=None))]
    fn new(py: Python, ctx: PyObject, strict_mode: Option<bool>, audit_recipe: Option<PyObject>) -> Self {
        let is_strict = strict_mode.unwrap_or(false);
        let mut policy = None;
        if let Some(recipe) = audit_recipe {
             if let Ok(p) = AuditPolicy::from_python(py, recipe) {
                 policy = Some(p);
             } else {
                 eprintln!("WARNING: Failed to parse Audit Policy");
             }
        }

        Engine {
            ctx,
            // process_registry: HashMap::new(),
            audit_policy: policy,
            strict_mode: is_strict,
        }
    }
    
    fn register_process(&mut self, name: String, func: PyObject) {
        registry::register_process(name, func);
    }

    #[pyo3(signature = (process_name, **kwargs))]
    fn execute_process(&mut self, py: Python, process_name: String, kwargs: Option<&Bound<'_, pyo3::types::PyDict>>) -> PyResult<PyObject> {
        let func = registry::get_process(py, &process_name)
            .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(format!("Process '{}' not found", process_name)))?;
        
        let ctx_bound = self.ctx.bind(py);

        if let Some(policy) = &mut self.audit_policy {
             if let Err(e) = policy.evaluate(py, &process_name, "input", ctx_bound, None) {
                  return Self::raise_audit_error(py, e);
             }
        }
        
        // Transaction (New PyClass)
        // [FIX] Conditional Initialization: Only create Transaction if strict_mode is TRUE
        let tx = if self.strict_mode {
            Some(Py::new(py, Transaction::new())?)
        } else {
            None
        };

        let func_bound = func.bind(py);
        let contract = func_bound.getattr("_pop_contract")
             .map_err(|_| pyo3::exceptions::PyAttributeError::new_err(format!("Process '{}' usually needs @process decorator", process_name)))?;
             
        let inputs = contract.getattr("inputs")?.extract::<Vec<String>>()?;
        let outputs = contract.getattr("outputs")?.extract::<Vec<String>>()?;
        let declared_errors = contract.getattr("errors")?.extract::<Vec<String>>()?;
        
        // ContextGuard(ctx, inputs, outputs, "", tx)
        // Use the RUST ContextGuard directly for performance and correctness
        let guard_struct = ContextGuard::new_internal(
            self.ctx.clone_ref(py), 
            inputs, 
            outputs, 
            tx.as_ref().map(|t| t.clone_ref(py)),
            false, // Process Guard is NOT admin
            self.strict_mode,
        )?;
        let guard = Py::new(py, guard_struct)?;
        
        let args = (guard,);
        let result = match func_bound.call(args, kwargs) {
            Ok(res) => res.unbind(),
            Err(e) => {
                if let Some(tx) = &tx {
                     let tx_bound = tx.bind(py);
                     tx_bound.borrow_mut().rollback(py)?; 
                } 
                
                // Check if error is declared or is a ContractViolationError
                let err_type = e.get_type(py).name()?.to_string();
                if declared_errors.contains(&err_type) {
                     return Err(e);
                }
                
                // Allow builtin PermissionError (mapped from our PyPermissionError) to pass?
                // Or wrap it?
                // If it is PermissionError, it means Guard blocked it. Is it a Contract Violation?
                // Yes, but Python test might expect ContractViolationError.
                // But generally PermissionError IS the enforcement.
                
                // If it is ALREADY ContractViolationError (from FrozenList etc), allow it.
                if err_type == "ContractViolationError" || err_type == "PermissionError" {
                     return Err(e);
                }

                // Otherwise, wrap as Undeclared Error Violation
                let contracts_mod = PyModule::import(py, "theus.contracts")?;
                let exc = contracts_mod.getattr("ContractViolationError")?;
                let msg = format!("Undeclared Error Violation: Caught {}: {}", err_type, e);
                return Err(PyErr::from_value(exc.call1((msg,))?));
            }
        };
        
        if let Some(policy) = &mut self.audit_policy {
            // Use Admin Guard to allow Audit to see Shadows and Read All
            let audit_guard_struct = ContextGuard::new_internal(
                self.ctx.clone_ref(py),
                vec![], // inputs ignored in admin
                vec![], // outputs ignored in admin
                tx.as_ref().map(|t| t.clone_ref(py)),
                true, // IS ADMIN
                self.strict_mode,
            )?;
            let audit_guard = Py::new(py, audit_guard_struct)?;

            if let Err(e) = policy.evaluate(py, &process_name, "output", audit_guard.bind(py), None) {
                  if let Some(tx) = &tx {
                      let tx_bound = tx.bind(py);
                      tx_bound.borrow_mut().rollback(py)?;
                  }
                  return Self::raise_audit_error(py, e);
            }
        }
        
        if let Some(tx) = &tx {
             let tx_bound = tx.bind(py);
             tx_bound.borrow_mut().commit(py)?;
        }

        Ok(result)
    }
        #[pyo3(signature = (step, **kwargs))]
    fn execute_flux_step(&mut self, py: Python, step: PyObject, kwargs: Option<&Bound<'_, pyo3::types::PyDict>>) -> PyResult<()> {
        // Resolve Step Type
        if let Ok(name) = step.extract::<String>(py) {
             self.execute_process(py, name, kwargs)?;
             return Ok(());
        }

        if let Ok(dict) = step.bind(py).downcast::<pyo3::types::PyDict>() {
             // 1. Process Call
             if let Some(sub_name) = dict.get_item("process")? {
                 let name = sub_name.extract::<String>()?;
                 self.execute_process(py, name, kwargs)?;
                 return Ok(());
             }

             // 2. Flux Control
             if let Some(flux_type) = dict.get_item("flux")? {
                 let f_type = flux_type.extract::<String>()?;
                 
                 if f_type == "run" {
                     if let Some(steps) = dict.get_item("steps")? {
                         let steps_list = steps.downcast::<pyo3::types::PyList>()?;
                         for s in steps_list.iter() {
                             self.execute_flux_step(py, s.unbind(), kwargs)?;
                         }
                     }
                 }
                 else if f_type == "if" {
                     let condition = dict.get_item("condition")?.map(|s| s.extract::<String>()).transpose()?.unwrap_or("False".to_string());
                     if self.evaluate_condition(py, &condition)? {
                         if let Some(steps) = dict.get_item("then")? {
                             let steps_list = steps.downcast::<pyo3::types::PyList>()?;
                             for s in steps_list.iter() {
                                 self.execute_flux_step(py, s.unbind(), kwargs)?;
                             }
                         }
                     } else if let Some(steps) = dict.get_item("else")? {
                         let steps_list = steps.downcast::<pyo3::types::PyList>()?;
                         for s in steps_list.iter() {
                             self.execute_flux_step(py, s.unbind(), kwargs)?;
                         }
                     }
                 }
                 else if f_type == "while" {
                     let condition = dict.get_item("condition")?.map(|s| s.extract::<String>()).transpose()?.unwrap_or("False".to_string());
                     // Loop Limit Safety? 
                     // TODO: Implement max_ops counter from Python equivalent
                     let mut safety = 0;
                     while self.evaluate_condition(py, &condition)? {
                         safety += 1;
                         if safety > 10000 {
                             return Err(pyo3::exceptions::PyRuntimeError::new_err("Flux Loop Safety Trip"));
                         }
                         
                         if let Some(steps) = dict.get_item("do")? {
                             let steps_list = steps.downcast::<pyo3::types::PyList>()?;
                             for s in steps_list.iter() {
                                 self.execute_flux_step(py, s.unbind(), kwargs)?;
                             }
                         }
                     }
                 }
             }
        }
        Ok(())
    }

    fn evaluate_condition(&self, py: Python, condition: &str) -> PyResult<bool> {
        // Construct safe locals mostly matches Python logic
        let locals = pyo3::types::PyDict::new(py);
        locals.set_item("ctx", self.ctx.bind(py))?;
        // We try to access domain/global from ctx if they exist
        if let Ok(domain) = self.ctx.bind(py).getattr("domain_ctx") {
            locals.set_item("domain", domain)?;
        }
        if let Ok(global) = self.ctx.bind(py).getattr("global_ctx") {
            locals.set_item("global", global)?;
        }
        // Minimal builtins
        // py.eval handles this if we pass strict globals?
        // Let's use py.eval(condition, None, locals)
        
        // Execute Python eval safely
        // PyO3 0.23 eval requires &CStr
        let c_cond = std::ffi::CString::new(condition)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid CString: {}", e)))?;
            
        let res = py.eval(&c_cond, None, Some(&locals))?;
        let val: bool = res.extract()?;
        Ok(val)
    }
    
    #[pyo3(signature = (steps, **kwargs))]
    fn execute_workflow(&mut self, py: Python, steps: PyObject, kwargs: Option<&Bound<'_, pyo3::types::PyDict>>) -> PyResult<PyObject> {
        let steps_list = steps.bind(py).downcast::<pyo3::types::PyList>()?;
        for step in steps_list.iter() {
             self.execute_flux_step(py, step.unbind(), kwargs)?;
        }
        Ok(self.ctx.clone_ref(py))
    }
}

