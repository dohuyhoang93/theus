use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use log::warn;
use pyo3::prelude::*;
use pyo3::types::PyAny;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleSpec {
    pub target_field: String,
    pub condition: String,
    pub value: serde_json::Value, 
    pub level: String, 
    pub min_threshold: u32,
    pub max_threshold: u32,
    pub reset_on_success: bool,
    pub message: Option<String>,
}

#[derive(Debug, Clone)]
pub enum AuditError {
    Interlock(String),
    Block(String),
}

pub struct AuditTracker {
    pub counters: HashMap<String, u32>,
}

impl AuditTracker {
    pub fn new() -> Self {
        Self {
            counters: HashMap::new(),
        }
    }

    pub fn increment(&mut self, key: &str) -> u32 {
        let count = self.counters.entry(key.to_string()).or_insert(0);
        *count += 1;
        *count
    }

    pub fn reset(&mut self, key: &str) {
        if let Some(count) = self.counters.get_mut(key) {
            *count = 0;
        }
    }
}

pub struct AuditPolicy {
    pub input_rules: HashMap<String, Vec<RuleSpec>>,
    pub output_rules: HashMap<String, Vec<RuleSpec>>,
    pub tracker: AuditTracker,
}

impl AuditPolicy {
    pub fn new() -> Self {
        Self {
            input_rules: HashMap::new(),
            output_rules: HashMap::new(),
            tracker: AuditTracker::new(),
        }
    }

    pub fn from_python(py: Python, recipe: PyObject) -> PyResult<Self> {
        let recipe_bound = recipe.bind(py);
        let definitions = recipe_bound.getattr("definitions")?.extract::<HashMap<String, PyObject>>()?;
        
        let mut policy = AuditPolicy::new();
        
        for (process_name, spec_obj) in definitions {
            let spec = spec_obj.bind(py);
            
            // Input Rules
            if let Ok(inputs) = spec.getattr("input_rules") {
                if let Ok(rules_list) = inputs.extract::<Vec<PyObject>>() {
                   let mut rules = Vec::new();
                   for r_obj in rules_list {
                       rules.push(Self::parse_rule(py, r_obj.bind(py))?);
                   }
                   policy.input_rules.insert(process_name.clone(), rules);
                }
            }
            
            // Output Rules
            if let Ok(outputs) = spec.getattr("output_rules") {
                if let Ok(rules_list) = outputs.extract::<Vec<PyObject>>() {
                   let mut rules = Vec::new();
                   for r_obj in rules_list {
                       rules.push(Self::parse_rule(py, r_obj.bind(py))?);
                   }
                   policy.output_rules.insert(process_name.clone(), rules);
                }
            }
        }
        
        Ok(policy)
    }

    fn parse_rule(_py: Python, rule_obj: &Bound<'_, PyAny>) -> PyResult<RuleSpec> {
        let target_field = rule_obj.getattr("target_field")?.extract::<String>()?;
        let condition = rule_obj.getattr("condition")?.extract::<String>()?;
        let level = rule_obj.getattr("level")?.extract::<String>()?;
        let min_threshold = rule_obj.getattr("min_threshold")?.extract::<u32>().unwrap_or(0);
        let max_threshold = rule_obj.getattr("max_threshold")?.extract::<u32>().unwrap_or(1);
        let reset_on_success = rule_obj.getattr("reset_on_success")?.extract::<bool>().unwrap_or(true);
        let message = rule_obj.getattr("message")?.extract::<Option<String>>().unwrap_or(None);
        
        let val_obj = rule_obj.getattr("value")?;
        let value = Self::py_to_json(val_obj)?;

        Ok(RuleSpec {
            target_field,
            condition,
            value,
            level,
            min_threshold,
            max_threshold,
            reset_on_success,
            message,
        })
    }

    fn py_to_json(val: Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
        if val.is_none() {
            return Ok(serde_json::Value::Null);
        }
        if let Ok(b) = val.extract::<bool>() {
            return Ok(serde_json::Value::Bool(b));
        }
        if let Ok(i) = val.extract::<i64>() {
            return Ok(serde_json::json!(i));
        }
        if let Ok(f) = val.extract::<f64>() {
            return Ok(serde_json::json!(f));
        }
        if let Ok(s) = val.extract::<String>() {
            return Ok(serde_json::Value::String(s));
        }
        // Fallback to string representation for complex types
        Ok(serde_json::Value::String(val.to_string()))
    }
    
    // Use Bound<'py, PyAny>
    fn resolve_path<'a>(&self, _py: Python<'a>, ctx: &Bound<'a, PyAny>, path: &str, extra_data: Option<&Bound<'a, PyAny>>) -> PyResult<Option<Bound<'a, PyAny>>> {
        if let Some(data) = extra_data {
            if let Ok(val) = data.get_item(path) {
                 return Ok(Some(val));
            }
        }

        let mut current = ctx.clone();
        for part in path.split('.') {
            if let Some(method_name) = part.strip_suffix("()") {
                let obj = current.getattr(method_name)?;
                current = obj.call0()?;
            } else if let Ok(attr) = current.getattr(part) {
                current = attr;
            } else if let Ok(item) = current.get_item(part) {
                 current = item;
            } else {
                 return Ok(None); 
            }
        }
        Ok(Some(current))
    }
    
    fn check_condition(&self, actual: &Bound<'_, PyAny>, condition: &str, limit_val: &serde_json::Value) -> bool {
        match condition {
            "min" => {
                if let Ok(val) = actual.extract::<f64>() {
                    if let Some(limit) = limit_val.as_f64() {
                        return val >= limit;
                    }
                }
            },
            "max" => {
                if let Ok(val) = actual.extract::<f64>() {
                    if let Some(limit) = limit_val.as_f64() {
                        return val <= limit;
                    }
                }
            },
            "eq" => {
                 if let Some(s) = limit_val.as_str() {
                     let actual_str = actual.to_string();
                     return actual_str == s;
                 }
            },
             "neq" => {
                 if let Some(s) = limit_val.as_str() {
                     let actual_str = actual.to_string();
                     return actual_str != s;
                 }
             },
            "min_len" => {
                if let Ok(len) = actual.len() {
                    if let Some(limit) = limit_val.as_u64() {
                        return len >= (limit as usize);
                    }
                }
            },
            "max_len" => {
                if let Ok(len) = actual.len() {
                    if let Some(limit) = limit_val.as_u64() {
                        return len <= (limit as usize);
                    }
                }
            }
            _ => return true, 
        }
        true
    }

    pub fn evaluate<'a>(&mut self, py: Python<'a>, process_name: &str, stage: &str, ctx: &Bound<'a, PyAny>, extra_data: Option<&Bound<'a, PyAny>>) -> Result<(), AuditError> {
        let rules = if stage == "input" {
            self.input_rules.get(process_name).cloned()
        } else {
            self.output_rules.get(process_name).cloned()
        };
        
        if let Some(rule_list) = rules {
            for rule in rule_list {
                let actual_val_opt = self.resolve_path(py, ctx, &rule.target_field, extra_data).unwrap_or(None);
                
                let passed = if let Some(val) = &actual_val_opt {
                    self.check_condition(val, &rule.condition, &rule.value)
                } else {
                    true 
                };
                
                if !passed {
                    let key = format!("{}:{}:{}", process_name, rule.target_field, rule.condition);
                    let count = self.tracker.increment(&key);
                    
                    let actual_str = actual_val_opt.map(|v| v.to_string()).unwrap_or("None".to_string());
                    
                    if count >= rule.max_threshold {
                         self.tracker.reset(&key);
                         let default_msg = format!("[{}] Rule '{}' violated on '{}'. Value={}. Level {}", stage, rule.condition, rule.target_field, actual_str, rule.level);
                         let msg = rule.message.clone().unwrap_or(default_msg);
                         
                         match rule.level.as_str() {
                             "S" | "A" => return Err(AuditError::Interlock(msg)),
                             "B" => return Err(AuditError::Block(msg)),
                             _ => warn!("{}", msg),
                         }
                     } else if count >= rule.min_threshold {
                        warn!("[EARLY WARNING] Rule '{}' violated on '{}'. Count: {}", rule.condition, rule.target_field, count);
                     }
                } else if rule.reset_on_success { 
                    let key = format!("{}:{}:{}", process_name, rule.target_field, rule.condition);
                    self.tracker.reset(&key);
                }
            }
        }
        
        Ok(())
    }
}
