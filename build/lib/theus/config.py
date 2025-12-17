
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
@dataclass
class RuleSpec:
    target_field: str
    condition: str # e.g., "min", "max", "regex"
    value: Any
    level: str # S, A, B, C
    threshold: int = 1 # For A/B levels

@dataclass
class ProcessRecipe:
    process_name: str
    input_rules: List[RuleSpec] = field(default_factory=list)
    output_rules: List[RuleSpec] = field(default_factory=list)
    inherits: Optional[str] = None

@dataclass
class AuditRecipe:
    definitions: Dict[str, ProcessRecipe] = field(default_factory=dict)
    # Mapping could be handled here or in the definitions themselves via inheritance resolving

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
        Returns AuditRecipe object containing {process_name: ProcessRecipe}
        """
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            raw_defs = data.get('process_recipes', {})
            resolved = {}

            # Simple 1-pass resolution (Naive - assumes order or simple dependency)
            # Todo: Implement topological sort for deep inheritance if needed.
            
            for name, spec in raw_defs.items():
                # Parse raw dict to object
                recipe = ProcessRecipe(process_name=name)
                
                # Handle Inheritance
                parent_name = spec.get('inherits')
                if parent_name and parent_name in raw_defs:
                    # simplistic copy from parent spec dict
                    parent_spec = raw_defs[parent_name]
                    # Merge logic would go here
                    recipe.inherits = parent_name
                
                # Parse Rules
                for rule_data in spec.get('inputs', []):
                     recipe.input_rules.append(ConfigFactory._parse_rule(rule_data))
                for rule_data in spec.get('outputs', []):
                     recipe.output_rules.append(ConfigFactory._parse_rule(rule_data))

                resolved[name] = recipe
            
            return AuditRecipe(definitions=resolved)

        except Exception as e:
            raise ConfigError(f"Failed to load Recipe from {path}: {e}")

    @staticmethod
    def _parse_rule(data: Dict) -> RuleSpec:
        # Example data: {field: "age", min: 18, level: "S"}
        # Needs to be normalized to RuleSpec
        # For MVP, we stick to a simple structure
        level = data.get('level', 'C')
        target = data.get('field')
        
        # Extract condition (first key that is not field/level/threshold)
        reserved = {'field', 'level', 'threshold'}
        condition = next((k for k in data.keys() if k not in reserved), 'exists')
        value = data.get(condition)
        
        return RuleSpec(
            target_field=target,
            condition=condition,
            value=value,
            level=level,
            threshold=data.get('threshold', 1)
        )
