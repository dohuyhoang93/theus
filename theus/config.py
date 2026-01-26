from typing import Any, Dict
from dataclasses import dataclass
# Re-export from Rust Core
try:
    from theus_core import ConfigLoader, SchemaViolationError, AuditRecipe
except ImportError:
    class SchemaViolationError(Exception): pass
    class AuditRecipe:
        def __init__(self, threshold_max=3, reset_on_success=True): pass
    class ConfigLoader:
        @staticmethod
        def load_from_string(content: str): pass

@dataclass
class AuditRecipeBook:
    """
    Hybrid Wrapper: Holds Python Dictionary (for CLI/Inspection) 
    AND Rust AuditRecipe (for Engine).
    """
    definitions: Dict[str, Any]
    rust_recipe: AuditRecipe

    def __getattr__(self, name):
        # Proxy to Rust Recipe (for Engine compatibility)
        return getattr(self.rust_recipe, name)

class ConfigFactory:
    @staticmethod
    def load_audit_recipe():
        """Attempts to load audit_recipe.yaml from CWD."""
        import os
        import yaml
        
        path = "audit_recipe.yaml"
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return data
            except Exception as e:
                print(f"WARNING: Failed to load audit_recipe.yaml: {e}")
        return None

    @staticmethod
    def load_recipe(path: str) -> AuditRecipeBook:
        import yaml
        import os
        if not os.path.exists(path):
            raise FileNotFoundError(f"Recipe not found: {path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            
        # 1. Parse for Python Logic (Introspection)
        definitions = {}
        if 'process_recipes' in data:
            # Map "p_name" -> Rules
            # In V3 YAML, it might be nested. 
            # We assume structure: { process_recipes: { name: { inputs: [], ... } } }
            definitions = data['process_recipes']

        # 2. Parse for Rust Logic (Engine)
        target = data
        if 'audit' in data:
            target = data['audit']
            
        t_max = target.get('threshold_max', target.get('max_retries', 3))
        reset = target.get('reset_on_success', True)
        
        rust_recipe = AuditRecipe(threshold_max=int(t_max), reset_on_success=bool(reset))
        
        return AuditRecipeBook(definitions=definitions, rust_recipe=rust_recipe)

__all__ = ["ConfigLoader", "SchemaViolationError", "ConfigFactory", "AuditRecipe"]
