from typing import Any, Dict, List, Optional
import re
import logging

# [DX] Use theus.audit wrapper for consistency
from theus.audit import AuditSystem

logger = logging.getLogger(__name__)

class AuditValidator:
    """
    [v3.1.2] Active Policy Enforcer.
    Parses 'process_recipes' from audit_recipe.yaml and enforces rules
    via the AuditSystem (which handles Counters, Levels, and RingBuffer).
    """

    def __init__(self, definitions: Dict[str, Any], audit_system: AuditSystem):
        self.definitions = definitions or {}
        self.audit_system = audit_system

    def validate_inputs(self, func_name: str, kwargs: Dict[str, Any]) -> None:
        """
        Input Gate: Checks function arguments against defined rules.
        """
        recipe = self.definitions.get(func_name)
        if not recipe or "inputs" not in recipe:
            return

        input_rules = recipe["inputs"]
        for rule in input_rules:
            field = rule.get("field")
            if not field or field not in kwargs:
                continue

            value = kwargs[field]
            self._check_rule(func_name, f"input:{field}", value, rule)

    def validate_outputs(self, func_name: str, pending_data: Dict[str, Any]) -> None:
        """
        Output Gate: Checks pending state mutations against defined rules.
        """
        recipe = self.definitions.get(func_name)
        if not recipe or "outputs" not in recipe:
            return

        output_rules = recipe["outputs"]
        for rule in output_rules:
            field_path = rule.get("field")
            if not field_path:
                continue

            # Resolve value from pending_data (dot notation)
            value = self._resolve_path(pending_data, field_path)
            if value is None:
                continue

            self._check_rule(func_name, f"output:{field_path}", value, rule)

    def _check_rule(self, func_name: str, key_suffix: str, value: Any, rule: Dict[str, Any]) -> None:
        """
        Core Validation Logic.
        Triggers audit_system.log_fail() on violation.
        """
        violation = None

        # 1. Numeric Checks
        if isinstance(value, (int, float)):
            if "min" in rule and value < rule["min"]:
                violation = f"Value {value} < min {rule['min']}"
            elif "max" in rule and value > rule["max"]:
                violation = f"Value {value} > max {rule['max']}"
            elif "eq" in rule and value != rule["eq"]:
                violation = f"Value {value} != {rule['eq']}"
            elif "neq" in rule and value == rule["neq"]:
                violation = f"Value {value} == {rule['neq']} (Forbidden)"

        # 2. Length Checks (Strings, Lists, Dicts)
        if hasattr(value, "__len__"):
            length = len(value)
            if "min_len" in rule and length < rule["min_len"]:
                violation = f"Length {length} < min_len {rule['min_len']}"
            elif "max_len" in rule and length > rule["max_len"]:
                violation = f"Length {length} > max_len {rule['max_len']}"

        # 3. Regex Checks (Strings)
        if isinstance(value, str) and "regex" in rule:
            pattern = rule["regex"]
            if not re.match(pattern, value):
                violation = f"Value '{value}' failed regex '{pattern}'"

        if violation:
            # Construct Audit Key: "process_name:input:field"
            audit_key = f"{func_name}:{key_suffix}"
            
            # Message
            msg = rule.get("message", violation)
            self.audit_system.log(audit_key, f"VIOLATION: {msg}")
            
            # [v3.1.3] Granular Audit Support (INC-012)
            # Map Spec string (S/A/B/C) to Rust Enum
            from theus.audit import AuditLevel
            
            level_map = {
                "S": AuditLevel.Stop,
                "A": AuditLevel.Abort,
                "B": AuditLevel.Block,
                "C": AuditLevel.Count
            }
            
            spec_level = rule.get("level")
            audit_level = level_map.get(spec_level) if spec_level else None
            
            # Threshold Override
            # Spec might use "max_threshold" or "threshold_max"
            spec_threshold = rule.get("max_threshold", rule.get("threshold_max"))
            threshold_override = int(spec_threshold) if spec_threshold is not None else None

            # Log Fail -> Increments Counter -> Check Level
            self.audit_system.log_fail(audit_key, level=audit_level, threshold_max=threshold_override)

    def _resolve_path(self, data: Dict[str, Any], path: str) -> Any:
        # Simple dot-notation resolver
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            
            if current is None:
                return None
        return current
