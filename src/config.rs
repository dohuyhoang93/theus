use pyo3::prelude::*;
use pyo3::create_exception;
use serde::Deserialize;
use std::collections::HashMap;

create_exception!(theus.config, SchemaViolationError, pyo3::exceptions::PyException);

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
#[allow(dead_code)]
struct RootConfig {
    context: Option<ContextConfig>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
#[allow(dead_code)]
struct ContextConfig {
    #[serde(default)]
    global: HashMap<String, FieldSpec>,
    #[serde(default)]
    domain: HashMap<String, FieldSpec>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
#[allow(dead_code)]
struct FieldSpec {
    #[serde(default = "default_type")]
    r#type: String,
    #[serde(default = "default_true")]
    required: bool,
    default: Option<String>, // Simplification: assume default is string repr or handle dynamic?
    // For V3 Schema, default can be any valid JSON/YAML value.
    // But Serde strongly types it.
    // Let's us serde_yaml::Value for flexible default.
}

fn default_type() -> String { "string".to_string() }
fn default_true() -> bool { true }

#[pyclass(module = "theus_core")]
pub struct ConfigLoader {}

#[pymethods]
impl ConfigLoader {
    #[staticmethod]
    fn load_from_string(content: String) -> PyResult<()> {
        let _config: RootConfig = serde_yaml::from_str(&content)
            .map_err(|e| SchemaViolationError::new_err(format!("Config Error: {}", e)))?;
        Ok(())
    }
}
