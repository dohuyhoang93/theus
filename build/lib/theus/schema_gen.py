import inspect
import typing
import yaml
import importlib.util
from pathlib import Path
from dataclasses import is_dataclass, fields
from typing import Any, Dict, Type

try:
    from pydantic import BaseModel
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    class BaseModel: pass

TYPE_MAP = {
    int: "integer",
    str: "string",
    float: "float",
    bool: "boolean",
    list: "list",
    dict: "dict"
}

def load_module_from_path(path: Path):
    """Dynamically loads a python module from a file path."""
    spec = importlib.util.spec_from_file_location("dynamic_context", path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None

def get_type_name(py_type: Any) -> str:
    """Maps Python type to YAML Schema type string."""
    origin = typing.get_origin(py_type)
    args = typing.get_args(py_type)

    # Handle Optional[T] -> T
    if origin is typing.Union and type(None) in args:
        # Extract the non-None type
        non_none = [t for t in args if t is not type(None)]
        if non_none:
            return get_type_name(non_none[0])

    if py_type in TYPE_MAP:
        return TYPE_MAP[py_type]
    
    # Handle List[T]
    if origin is list or origin is typing.List:
        return "list"
    
    # Handle Dict[K, V]
    if origin is dict or origin is typing.Dict:
        return "dict"

    # Fallback
    if hasattr(py_type, "__name__"):
        return py_type.__name__
    
    return str(py_type)

def is_optional(py_type: Any) -> bool:
    origin = typing.get_origin(py_type)
    args = typing.get_args(py_type)
    return origin is typing.Union and type(None) in args

from .zones import resolve_zone, ContextZone

# ... existing imports ...

def inspect_class(cls: Type) -> Dict[str, Any]:
    """Recursively inspects a Dataclass or Pydantic model."""
    schema = {}
    
    # 1. Pydantic Strategy
    if HAS_PYDANTIC and issubclass(cls, BaseModel):
        # Pydantic V1/V2 compatibility
        model_fields = getattr(cls, "model_fields", None) # V2
        if not model_fields:
            model_fields = getattr(cls, "__fields__", {}) # V1
            
        for name, field_info in model_fields.items():
            # [ZONE FILTER] Skip Signal/Meta
            if resolve_zone(name) != ContextZone.DATA:
                continue

            # Extract type
            f_type = getattr(field_info, "annotation", None) 
            if not f_type:
                f_type = getattr(field_info, "type_", Any) # V1
            
            type_str = get_type_name(f_type)
            entry = {"type": type_str}
            
            # Check recursive
            if is_dataclass(f_type) or (HAS_PYDANTIC and isinstance(f_type, type) and issubclass(f_type, BaseModel)):
                 entry["structure"] = inspect_class(f_type)
            
            if not is_optional(f_type):
                entry["required"] = True
                
            schema[name] = entry
            
    # 2. Dataclass Strategy
    elif is_dataclass(cls):
        for f in fields(cls):
            # [ZONE FILTER] Skip Signal/Meta
            if resolve_zone(f.name) != ContextZone.DATA:
                continue

            type_str = get_type_name(f.type)
            entry = {"type": type_str}
            
            # Recursive check
            # Real introspection of nested types is hard without value, 
            # relying on type hint inspection
            
            if not is_optional(f.type):
                entry["required"] = True

            # If default value exists
            if f.default != inspect.Parameter.empty:
                # Basic primitives only
                if isinstance(f.default, (int, str, bool, float)):
                    entry["default"] = f.default

            schema[f.name] = entry
            
    return schema

def generate_schema_from_file(file_path: str) -> Dict[str, Any]:
    """
    Main entry point. Loads file, finds 'SystemContext' or 'DomainContext', returns Dict.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Context file not found: {file_path}")
        
    module = load_module_from_path(p)
    if not module:
        raise ImportError(f"Could not load module: {file_path}")
        
    # Heuristic: Find class inheriting from BaseSystemContext
    from theus.context import BaseSystemContext
    target_cls = None
    
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            if issubclass(obj, BaseSystemContext):
                target_cls = obj
                break
                
    if not target_cls:
        # Fallback: exact name match still useful if BaseSystemContext import fails?
        target_cls = getattr(module, "SystemContext", getattr(module, "DomainContext", None))
    
    if not target_cls:
        raise ValueError("Could not find any class inheriting from 'BaseSystemContext' (or named 'SystemContext') in file.")

    print(f"   Found context class: {target_cls.__name__}")
    
    # Inspect
    # If SystemContext, it usually has 'domain', 'global', 'local'
    # We want to flatten this or respect structure
    
    raw_schema = inspect_class(target_cls)
    
    # [FALLBACK] If raw_schema is empty (because __init__ usage), try annotations
    if not raw_schema and hasattr(target_cls, '__annotations__'):
        annotations = target_cls.__annotations__
        if 'global_ctx' in annotations:
            raw_schema['global_ctx'] = {'structure': inspect_class(annotations['global_ctx'])}
        if 'domain_ctx' in annotations:
            raw_schema['domain_ctx'] = {'structure': inspect_class(annotations['domain_ctx'])}
            
    # [FALLBACK V2 - ENHANCED] 
    # IF raw_schema is empty OR if the detected structures are empty (due to Base Class inheritance),
    # Try to find better candidates in the module.
    
    need_global_fallback = False
    need_domain_fallback = False
    
    if not raw_schema:
        need_global_fallback = True
        need_domain_fallback = True
        raw_schema = {}
    else:
        # Check if global_ctx exists but is empty
        if 'global_ctx' in raw_schema:
            s = raw_schema['global_ctx'].get('structure', {})
            if not s: need_global_fallback = True
        elif 'global' not in raw_schema: # No global key at all
             need_global_fallback = True
             
        # Check if domain_ctx exists but is empty
        if 'domain_ctx' in raw_schema:
            s = raw_schema['domain_ctx'].get('structure', {})
            if not s: need_domain_fallback = True
        elif 'domain' not in raw_schema:
             need_domain_fallback = True

    if need_global_fallback or need_domain_fallback:
        print(f"   [SchemaGen] Attempting Heuristic Discovery for {'Global' if need_global_fallback else ''} {'Domain' if need_domain_fallback else ''}...")
        
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and obj.__module__ == module.__name__:
                # Discovery Strategy for Global
                if need_global_fallback:
                    if name.endswith('Global') or name == 'AppGlobal':
                        print(f"   [SchemaGen] Discovered Global Class: {name}")
                        raw_schema['global_ctx'] = {'structure': inspect_class(obj)}
                        need_global_fallback = False # Stop after first match? Maybe better to find "AppGlobal"? sticking to first relevant.

                # Discovery Strategy for Domain
                if need_domain_fallback:
                    if name.endswith('Domain') or name == 'AppDomain':
                         print(f"   [SchemaGen] Discovered Domain Class: {name}")
                         raw_schema['domain_ctx'] = {'structure': inspect_class(obj)}
                         need_domain_fallback = False
                         
    # Cleanup Debug Prints
    # ...
    
    # Re-structure for POP Schema format
    # context:
    #   global: ...
    #   domain: ...
    
    final_schema = {"context": {}}
    
    if "domain" in raw_schema:
        # If the class had a 'domain' field which was a nested class
        # raw_schema['domain'] is {'type': 'DomainContext', 'structure': {...}}
        # But 'inspect_class' above put 'structure' in?
        # My simple inspect_class needs refinement for nested logic.
        pass 

    # For MVP: Let's assume we generated a flat field list for now, 
    # or rely on the user to have 'domain' field.
    
    # Wait, inspect_class returns fields.
    # If SystemContext has 'domain: DomainContext', then:
    # raw_schema = {'domain': {'type': 'DomainContext', 'structure': {...}}}
    
    # If SystemContext has 'domain_ctx' and 'global_ctx', extracting their structure
    if "domain_ctx" in raw_schema and "structure" in raw_schema["domain_ctx"]:
        final_schema["context"]["domain"] = raw_schema["domain_ctx"]["structure"]
    elif "domain" in raw_schema and "structure" in raw_schema["domain"]: # Support old naming if present
        final_schema["context"]["domain"] = raw_schema["domain"]["structure"]

    if "global_ctx" in raw_schema and "structure" in raw_schema["global_ctx"]:
        final_schema["context"]["global"] = raw_schema["global_ctx"]["structure"]
        
    return final_schema
