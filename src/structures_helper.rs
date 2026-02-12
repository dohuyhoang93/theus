use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// Path segment types for nested access
#[derive(Debug)]
enum PathSegment {
    Key(String),
    Index(usize),
}

/// Parse path like "domain.users[0].name" into segments
fn parse_path_segments(path: &str) -> Vec<PathSegment> {
    let mut segments = Vec::new();
    let mut current = String::new();
    let mut chars = path.chars().peekable();
    
    while let Some(c) = chars.next() {
        match c {
            '.' => {
                if !current.is_empty() {
                    segments.push(PathSegment::Key(current.clone()));
                    current.clear();
                }
            }
            '[' => {
                if !current.is_empty() {
                    segments.push(PathSegment::Key(current.clone()));
                    current.clear();
                }
                // Collect index
                let mut idx_str = String::new();
                while let Some(&next) = chars.peek() {
                    if next == ']' {
                        chars.next(); // consume ']'
                        break;
                    }
                    idx_str.push(chars.next().unwrap());
                }
                // Try parse as index, fallback to key
                if let Ok(idx) = idx_str.parse::<usize>() {
                    segments.push(PathSegment::Index(idx));
                } else {
                    // String key in brackets like ['key']
                    let key = idx_str.trim_matches(|c| c == '\'' || c == '"');
                    segments.push(PathSegment::Key(key.to_string()));
                }
            }
            _ => {
                current.push(c);
            }
        }
    }
    
    if !current.is_empty() {
        segments.push(PathSegment::Key(current));
    }
    
    segments
}

/// Set nested value in a dict/list based on path notation
/// Supports: "domain.users[0].name", "data['key']", "items.0"
pub fn set_nested_value(py: Python, root: &Py<PyDict>, path: &str, value: &PyObject) -> PyResult<()> {
    let segments = parse_path_segments(path);
    
    if segments.is_empty() {
        return Ok(());
    }
    
    let mut current: PyObject = root.clone_ref(py).into_py(py);
    
    for (i, segment) in segments.iter().enumerate() {
        let is_last = i == segments.len() - 1;
        
        match segment {
            PathSegment::Key(key) => {
                let current_bound = current.bind(py);
                
                if is_last {
                    if let Ok(dict) = current_bound.downcast::<PyDict>() {
                        // [v3.3] Unwrap Proxy if it's a leaf
                        let final_val = if let Ok(target) = value.bind(py).getattr("supervisor_target") {
                            target.unbind()
                        } else {
                            value.clone_ref(py)
                        };
                        dict.set_item(key, final_val)?;
                    } else if let Ok(target) = current_bound.getattr("supervisor_target") {
                         // Set on Proxy's target
                         if let Ok(target_dict) = target.downcast::<PyDict>() {
                             let final_val = if let Ok(v_target) = value.bind(py).getattr("supervisor_target") {
                                 v_target.unbind()
                             } else {
                                 value.clone_ref(py)
                             };
                             target_dict.set_item(key, final_val)?;
                         } else {
                             current_bound.setattr(key.as_str(), value)?;
                         }
                    } else {
                        // Fallback to setattr
                        match current_bound.setattr(key.as_str(), value) {
                            Ok(_) => {},
                            Err(_) => {
                                return Err(pyo3::exceptions::PyTypeError::new_err(
                                    format!("Cannot set key '{}' on non-dict type '{}'", key, current_bound.get_type().name().map(|n| n.to_string()).unwrap_or_else(|_| "unknown".to_string()))
                                ));
                            }
                        }
                    }
                } else {
                    // Navigate or create
                    if let Ok(dict) = current_bound.downcast::<PyDict>() {
                        if let Some(next_obj) = dict.get_item(key)? {
                            current = next_obj.unbind();
                        } else {
                            // Create dict for next level
                            let new_dict = PyDict::new_bound(py);
                            dict.set_item(key, &new_dict)?;
                            current = new_dict.unbind().into_py(py);
                        }
                    } else {
                        // Generic Fallback: Try attribute access (for Proxies/Guards)
                        match current_bound.getattr(key.as_str()) {
                            Ok(next_obj) => {
                                current = next_obj.unbind();
                            }
                            Err(_) => {
                                return Err(pyo3::exceptions::PyTypeError::new_err(
                                    format!("Cannot navigate key '{}' in non-dict type '{}'", key, current_bound.get_type().name().map(|n| n.to_string()).unwrap_or_else(|_| "unknown".to_string()))
                                ));
                            }
                        }
                    }
                }
            }
            PathSegment::Index(idx) => {
                let current_bound = current.bind(py);
                
                if is_last {
                    // Set value at index
                    if let Ok(list) = current_bound.downcast::<PyList>() {
                        if *idx < list.len() {
                            list.set_item(*idx, value)?;
                        } else {
                            // Extend list if needed
                            while list.len() <= *idx {
                                list.append(py.None())?;
                            }
                            list.set_item(*idx, value)?;
                        }
                    } else if let Ok(dict) = current_bound.downcast::<PyDict>() {
                        // Some dicts use numeric string keys
                        dict.set_item(idx.to_string(), value)?;
                    } else {
                        return Err(pyo3::exceptions::PyTypeError::new_err(
                            format!("Cannot set index [{}] on non-list/dict", idx)
                        ));
                    }
                } else {
                    // Navigate
                    if let Ok(list) = current_bound.downcast::<PyList>() {
                        if *idx < list.len() {
                            current = list.get_item(*idx)?.unbind();
                        } else {
                            return Err(pyo3::exceptions::PyIndexError::new_err(
                                format!("Index [{}] out of range", idx)
                            ));
                        }
                    } else {
                        return Err(pyo3::exceptions::PyTypeError::new_err(
                            format!("Cannot navigate index [{}] in non-list", idx)
                        ));
                    }
                }
            }
        }
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_path_segments() {
        let segs = parse_path_segments("domain.users[0].name");
        assert_eq!(segs.len(), 4);
    }
}


/// Deep Merge implementation (CoW-like):
/// - Clones the original dict (shallow copy of keys).
/// - Recursively merges nested dicts.
/// - Overwrites non-dict values.
pub fn deep_merge_cow(py: Python, target: PyObject, updates: &Bound<'_, PyDict>) -> PyResult<PyObject> {
    // If target is a Dict, we merge.
    if let Ok(target_dict) = target.bind(py).downcast::<PyDict>() {
        // Create a shallow copy of the target to avoid mutating the original (CoW)
        let new_dict = target_dict.copy()?;
        
        for (k, v) in updates {
            // [v3.3 Fix] Force Unwrap Proxies (if any)
            let v_unwrapped = if let Ok(target) = v.getattr("supervisor_target") {
                target
            } else {
                v.clone()
            };
            let v = &v_unwrapped;

            // Check if value is a dict (nested update)
            if let Ok(nested_update) = v.downcast::<PyDict>() {
                // Check if target has this key AND it is a dict
                if let Some(existing_val) = new_dict.get_item(&k)? {
                    if let Ok(_existing_dict) = existing_val.downcast::<PyDict>() {
                        // Recurse
                        let merged_val = deep_merge_cow(py, existing_val.unbind(), nested_update)?;
                        new_dict.set_item(&k, merged_val)?;
                    } else {
                        // Target key exists but is not a dict -> Overwrite
                        new_dict.set_item(&k, v)?;
                    }
                } else {
                    // Key missing in target -> Insert
                    new_dict.set_item(&k, v)?;
                }
            } else {
                // Value is not a dict -> Overwrite
                new_dict.set_item(&k, v)?;
            }
        }
        Ok(new_dict.unbind().into_py(py))
    } else {
        // Target is not a dict -> Overwrite completely with updates
        Ok(updates.clone().unbind().into_py(py))
    }
}


/// Deep Update In-Place (Recursive Merge):
/// - Modifies the target dict directly.
/// - Recursively merges nested dicts.
/// - Overwrites non-dict values.
/// - [v3.1.2] Supports Dot-Notation expansion for keys (e.g. "domain.nested")
pub fn deep_update_inplace(py: Python, target: &Bound<'_, PyDict>, updates: &Bound<'_, PyDict>) -> PyResult<()> {
    for (k, v) in updates {
        // [v3.3 Fix] Force Unwrap Proxies (if any)
        let v_unwrapped = if let Ok(target) = v.getattr("supervisor_target") {
            target
        } else {
            v.clone()
        };
        let v = &v_unwrapped;
        
        // Check for Dot-Notation (Path Expansion)
        let mut handled_as_path = false;
        if let Ok(k_str) = k.extract::<String>() {
            if k_str.contains('.') {
                 deep_update_at_path(py, target, &k_str, &v.clone().into_py(py))?;
                 handled_as_path = true;
            }
        }

        if handled_as_path { continue; }

        // Standard Nested Dict Merge
        if let Ok(nested_update) = v.downcast::<PyDict>() {
            if let Some(existing_val) = target.get_item(&k)? {
                if let Ok(existing_dict) = existing_val.downcast::<PyDict>() {
                    // Recurse
                    deep_update_inplace(py, existing_dict, nested_update)?;
                } else {
                    target.set_item(&k, v)?;
                }
            } else {
                target.set_item(&k, v)?;
            }
        } else {
            // [v3.3 FIX] Unwrap Proxy before setting
            let final_val = if let Ok(target) = v.getattr("supervisor_target") {
                target.unbind().into_py(py)
            } else {
                v.clone().unbind().into_py(py)
            };
            target.set_item(&k, final_val)?;
        }
    }
    Ok(())
}

/// Helper: Update a nested value at path, performing deep merge at leaf if possible.
fn deep_update_at_path(py: Python, root: &Bound<'_, PyDict>, path: &str, value: &PyObject) -> PyResult<()> {
    let segments = parse_path_segments(path);
    if segments.is_empty() { return Ok(()); }
    
    let mut current: PyObject = root.clone().unbind().into_py(py);
    
    for (i, segment) in segments.iter().enumerate() {
        let is_last = i == segments.len() - 1;
        
        match segment {
             PathSegment::Key(key) => {
                 let current_bound = current.bind(py);
                 
                 if let Ok(dict) = current_bound.downcast::<PyDict>() {
                     if is_last {
                         // Leaf Logic: Merge or Overwrite
                         if let Ok(nested_update) = value.bind(py).downcast::<PyDict>() {
                              if let Some(existing_val) = dict.get_item(key)? {
                                   if let Ok(existing_dict) = existing_val.downcast::<PyDict>() {
                                        // Recurse Merge
                                        deep_update_inplace(py, existing_dict, nested_update)?;
                                        return Ok(());
                                   }
                              }
                         }
                         // Fallback Overwrite
                         dict.set_item(key, value)?;
                     } else {
                         // Navigate/Create
                         if let Some(next_obj) = dict.get_item(key)? {
                              current = next_obj.unbind();
                         } else {
                              let new_dict = PyDict::new_bound(py);
                              dict.set_item(key, &new_dict)?;
                              current = new_dict.unbind().into_py(py);
                         }
                     }
                 } else {
                     // Generic Fallback: Try attribute access
                     match current_bound.getattr(key.as_str()) {
                         Ok(next_obj) => {
                             current = next_obj.unbind();
                         }
                         Err(_) => {
                             // Try supervisor_target fallback (Proxy)
                             if let Ok(target) = current_bound.getattr("supervisor_target") {
                                 if let Ok(next_obj) = target.getattr(key.as_str()) {
                                      current = next_obj.unbind();
                                      continue;
                                 }
                             }
                             return Err(pyo3::exceptions::PyTypeError::new_err(format!("Cannot navigate key '{}' in non-dict type '{}'", key, current_bound.get_type().name().map(|n| n.to_string()).unwrap_or_else(|_| "unknown".to_string()))));
                         }
                     }
                 }
             }
             PathSegment::Index(idx) => {
                 let current_bound = current.bind(py);
                 // Simple list navigation/extension (No deep merge for lists implemented)
                  if let Ok(list) = current_bound.downcast::<PyList>() {
                        if is_last {
                             if *idx < list.len() {
                                 list.set_item(*idx, value)?;
                             } else {
                                  while list.len() <= *idx { list.append(py.None())?; }
                                  list.set_item(*idx, value)?;
                             }
                        } else if *idx < list.len() {
                             current = list.get_item(*idx)?.unbind();
                        } else {
                             return Err(pyo3::exceptions::PyIndexError::new_err(format!("Index [{}] out of range", idx)));
                        }
                  } else {
                       // Support numeric dict keys too?
                       // Omitting for brevity unless crucial.
                       return Err(pyo3::exceptions::PyTypeError::new_err(format!("Index [{}] on non-list", idx)));
                  }
             }
        }
    }
    Ok(())
}

