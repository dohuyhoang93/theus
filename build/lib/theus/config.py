
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

# --- EXCEPTIONS ---
class ConfigError(Exception):
    pass

class SchemaViolationError(ConfigError):
    pass

# --- 1. CONTEXT SCHEMA (The Contract) ---
@dataclass
class FieldSpec:
    name: str
    type: str # 'int', 'float', 'string', 'list', 'dict'
    required: bool = True
    default: Any = None

@dataclass
class ContextSchema:
    global_fields: Dict[str, FieldSpec] = field(default_factory=dict)
    domain_fields: Dict[str, FieldSpec] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ContextSchema':
        def parse_fields(field_dict):
            return {
                k: FieldSpec(name=k, type=v.get('type', 'string'), 
                             required=v.get('required', True), 
                             default=v.get('default'))
                for k, v in field_dict.items()
            }
        return cls(
            global_fields=parse_fields(data.get('global', {})),
            domain_fields=parse_fields(data.get('domain', {}))
        )

# --- 2. AUDIT RECIPE (The Policy) ---
# --- 2. AUDIT RECIPE (The Policy) ---
@dataclass
class RuleSpec:
    target_field: str
    condition: str      # e.g., "min", "max", "regex"
    value: Any
    level: str = 'C'    # Severity: S, A, B, C, I (Info)
    
    # Advanced Counter Logic (Phase 2)
    min_threshold: int = 0  # Start Warning (Yellow)
    max_threshold: int = 1  # Trigger Action (Red)
    max_threshold: int = 1  # Trigger Action (Red)
    reset_on_success: bool = True # Auto-reset counter on success
    message: Optional[str] = None # Custom message

@dataclass
class ProcessRecipe:
    process_name: str
    input_rules: List[RuleSpec] = field(default_factory=list)
    output_rules: List[RuleSpec] = field(default_factory=list)
    
    # V2 Semantics
    side_effects: List[str] = field(default_factory=list) 
    errors: List[str] = field(default_factory=list)       
    inherits: Optional[str] = None

@dataclass
class AuditRecipe:
    definitions: Dict[str, ProcessRecipe] = field(default_factory=dict)

# --- 3. LOADER FACTORY ---
class ConfigFactory:
    @staticmethod
    def load_schema(path: str) -> ContextSchema:
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}

            # Handle optional root 'context' key (Standard V2 format)
            if 'context' in data and isinstance(data['context'], dict):
                data = data['context']

            return ContextSchema.from_dict(data)
        except Exception as e:
            raise ConfigError(f"Failed to load Schema from {path}: {e}")

    @staticmethod
    def load_recipe(path: str) -> AuditRecipe:
        """
        Loads recipe and resolves inheritance.
        Returns AuditRecipe.
        """
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            raw_defs = data.get('process_recipes', {})
            resolved = {}

            for name, spec in raw_defs.items():
                recipe = ProcessRecipe(process_name=name)
                
                # Inheritance
                parent_name = spec.get('inherits')
                if parent_name and parent_name in raw_defs:
                    # TODO: True recursive merge. For now, we assume simple templates.
                    recipe.inherits = parent_name
                
                # Parse Rules (Using Smart Splitting)
                # Input Rules
                for rule_data in spec.get('inputs', []):
                    # rule_data is dict: {field: "age", min: 10, max: 20}
                    rules = ConfigFactory._parse_rules_from_dict(rule_data)
                    recipe.input_rules.extend(rules)
                    
                # Output Rules
                for rule_data in spec.get('outputs', []):
                    rules = ConfigFactory._parse_rules_from_dict(rule_data)
                    recipe.output_rules.extend(rules)

                # Semantics
                recipe.side_effects = spec.get('side_effects', [])
                recipe.errors = spec.get('errors', [])

                resolved[name] = recipe
            
            return AuditRecipe(definitions=resolved)

        except Exception as e:
            raise ConfigError(f"Failed to load Recipe from {path}: {e}")

    @staticmethod
    def _parse_rules_from_dict(data: Dict) -> List[RuleSpec]:
        """
        Phase 2 Parser: Extracts MULTIPLE rules from a single dictionary.
        Input: {field: "age", min: 18, max: 60, level: "A", threshold: 3}
        Output: [
            RuleSpec(field="age", condition="min", value=18, ...),
            RuleSpec(field="age", condition="max", value=60, ...)
        ]
        """
        target = data.get('field')  # Required
        if not target:
            # Fallback for old format or malformed rule?
            return []
            
        level = data.get('level', 'C')
        
        # Threshold handling (Backwards Compatibility)
        # Old: threshold=X applies to 'fail condition'.
        # New: min_threshold, max_threshold.
        raw_threshold = data.get('threshold', 1)
        min_threshold = data.get('min_threshold', 0)
        max_threshold = data.get('max_threshold', raw_threshold)
        reset = data.get('reset_on_success', True)
        
        extracted_rules = []
        
        # Reserved keys that are NOT conditions
        reserved = {
            'field', 'level', 'threshold', 
            'min_threshold', 'max_threshold', 'reset_on_success'
        }
        
        # Iterate over ALL keys in the dict
        for key, val in data.items():
            if key in reserved:
                continue
                
            # Create a RuleSpec for each condition found
            rule = RuleSpec(
                target_field=target,
                condition=key,
                value=val,
                level=level,
                min_threshold=min_threshold,
                max_threshold=max_threshold,
                reset_on_success=reset,
                message=data.get('message') # <--- Supporting Custom Message
            )
            extracted_rules.append(rule)
            
        # Default 'exists' rule if no condition provided? 
        # e.g. {field: "age"} -> just check existence/schema?
        if not extracted_rules and target:
             # Implicit 'exists' or 'schema' check could be added here.
             # For now, we return empty if no condition.
             pass
             
        return extracted_rules
