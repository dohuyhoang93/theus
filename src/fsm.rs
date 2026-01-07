use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use log::{info, warn};

#[pyclass]
pub struct StateMachine {
    states: PyObject, // Dict[str, Any]
    #[pyo3(get)]
    current_state: String,
}

#[pymethods]
impl StateMachine {
    #[new]
    #[pyo3(signature = (definition, start_state="IDLE".to_string()))]
    fn new(definition: PyObject, start_state: String) -> Self {
        StateMachine {
            states: definition,
            current_state: start_state,
        }
    }

    fn get_current_state(&self) -> String {
        self.current_state.clone()
    }

    fn trigger(&mut self, py: Python, event: String) -> PyResult<Vec<String>> {
        let states_dict = self.states.downcast_bound::<PyDict>(py)?;
        
        let state_def_any = match states_dict.get_item(&self.current_state)? {
            Some(s) => s,
            None => return Ok(vec![])
        };
        
        let state_def = state_def_any.downcast::<PyDict>()?;
        
        // Resolve Transitions
        let mut transitions_obj: Option<PyObject> = None;
        
        if let Some(events) = state_def.get_item("events")? {
            transitions_obj = Some(events.unbind());
        } else if let Some(on) = state_def.get_item("on")? {
             if on.extract::<bool>().is_ok() {
                 warn!("⚠️ FSM Warning: 'on' key parsed as Boolean. Use 'events' instead.");
             } else {
                 transitions_obj = Some(on.unbind());
             }
        } else if let Some(trans) = state_def.get_item("transitions")? {
            transitions_obj = Some(trans.unbind());
        }

        let next_state_name_obj = if let Some(obj) = transitions_obj {
            let t_bound = obj.bind(py).downcast::<PyDict>()?;
            t_bound.get_item(&event)?
        } else {
            None
        };

        let next_state_name = match next_state_name_obj {
            Some(s) => s.extract::<String>()?,
            None => return Ok(vec![])
        };

        info!("🔄 FSM Transition: {} --[{}]--> {}", self.current_state, event, next_state_name);
        self.current_state = next_state_name.clone();

        // Resolve Actions (Entry / Process)
        let new_state_def_any = match states_dict.get_item(&self.current_state)? {
             Some(s) => s,
             None => return Ok(vec![]) // Should not happen if config is valid
        };
        let new_state_def = new_state_def_any.downcast::<PyDict>()?;
        
        // Check "entry" first, then "process"
        let action_obj = if let Some(entry) = new_state_def.get_item("entry")? {
             Some(entry)
        } else {
             new_state_def.get_item("process")?
        };

        if let Some(act) = action_obj {
            if let Ok(s) = act.extract::<String>() {
                return Ok(vec![s]);
            } else if let Ok(l) = act.downcast::<PyList>() {
                return l.extract::<Vec<String>>();
            }
        }

        Ok(vec![])
    }
}
