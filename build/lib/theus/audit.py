
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from .config import RuleSpec, ProcessRecipe
import logging

logger = logging.getLogger("POP_AUDIT")

class AuditError(Exception):
    """Base for audit failures."""
    def __init__(self, message, rule: RuleSpec, current_val: Any):
        super().__init__(message)
        self.rule = rule
        self.current_val = current_val

class AuditInterlockError(AuditError):
    """Level S/A/B violation -> Stop Process."""
    pass

class AuditWarning(AuditError):
    """Level C violation -> Log Only."""
    pass

@dataclass
class ViolationState:
    count: int = 0
    
class AuditTracker:
    """Tracks violations over time for Threshold logic (A/B)."""
    def __init__(self):
        # Key: "process_name:field_name" -> ViolationState
        self._states: Dict[str, ViolationState] = {}

    def record_violation(self, key: str) -> int:
        if key not in self._states:
            self._states[key] = ViolationState()
        self._states[key].count += 1
        return self._states[key].count

    def reset(self, key: str):
        if key in self._states:
            self._states[key].count = 0

class AuditPolicy:
    """Implements the logic for S, A, B, C levels."""
    
    def __init__(self, tracker: AuditTracker):
        self.tracker = tracker

    def evaluate(self, rule: RuleSpec, value: Any, context_key: str):
        """
        Checks rule against value.
        If violated, decides action based on Level.
        """
        is_valid = self._check_condition(rule, value)
        if is_valid:
            # Optional: Reset counter on success? 
            # Industrial systems often auto-reset if 'n' successes occur. 
            # For simplicity MVP: we don't auto-reset yet.
            return

        # Handle Violation
        self._handle_violation(rule, value, context_key)

    def _check_condition(self, rule: RuleSpec, value: Any) -> bool:
        """
        Naive implementation of condition checking.
        """
        op = rule.condition
        target = rule.value

        try:
            if op == 'min': return value >= target
            if op == 'max': return value <= target
            if op == 'eq': return value == target
            if op == 'neq': return value != target
            if op == 'exists': return value is not None
        except TypeError:
            return False # Type mismatch usually implies violation
        return True

    def _handle_violation(self, rule: RuleSpec, value: Any, key: str):
        msg = f"Audit Violation: {rule.target_field} ({value}) failed {rule.condition} {rule.value}"
        
        # [LEVEL I] IGNORE (Explicit Bypass)
        if rule.level == 'I':
            return 

        # [LEVEL S] SERIOUS (Interlock)
        if rule.level == 'S':
            logger.error(f"[LEVEL S] INTERLOCK: {msg}")
            raise AuditInterlockError(msg, rule, value)

        # Threshold Tracking
        count = self.tracker.record_violation(key)

        # [LEVEL C] CONTINUE (Warning with Throttling)
        if rule.level == 'C':
            # Log only on 1st, 10th, 100th... violation to prevent flooding
            # Simple heuristic: count == 1 or count % 10 == 0 (or powers of 10)
            if count == 1 or (count < 100 and count % 10 == 0) or (count % 100 == 0):
                 logger.warning(f"[LEVEL C] {msg} (Count: {count})")
            return

        # [LEVEL A/B] THRESHOLD INTERLOCK
        limit = rule.threshold
        
        if count > limit:
            logger.error(f"[LEVEL {rule.level}] INTERLOCK: {msg} (Violations: {count}/{limit})")
            raise AuditInterlockError(msg, rule, value)
        else:
             # Also throttle warning for A/B if they have high limits?
             # Usually limits are small (3-5), so always logging is defined behavior.
             logger.warning(f"[LEVEL {rule.level}] WARNING: {msg} (Violations: {count}/{limit}) - System allowed to continue.")

class ContextAuditor:
    """Middleware injected into Engine."""
    def __init__(self, recipes: Dict[str, ProcessRecipe], tracker: AuditTracker = None):
        self.recipes = recipes
        self.tracker = tracker or AuditTracker()
        self.policy = AuditPolicy(self.tracker)

    def audit_input(self, process_name: str, context: Any, input_args: Dict[str, Any] = None):
        """
        Kiểm tra Inputs (Phase 1).
        Hỗ trợ check cả Context Fields và Input Arguments (kwargs).
        """
        self._audit_phase(process_name, context, 'inputs', input_args)

    def audit_output(self, process_name: str, context: Any, output_args: Dict[str, Any] = None):
        """
        Kiểm tra Outputs (Phase 2).
        """
        self._audit_phase(process_name, context, 'outputs', output_args)

    def _audit_phase(self, process_name: str, context: Any, phase: str, extra_scope: Dict[str, Any] = None):
        recipe = self.recipes.get(process_name)
        if not recipe:
            return

        rules = recipe.input_rules if phase == 'inputs' else recipe.output_rules
        if not rules:
            return

        for rule in rules:
            # 1. Resolve Value
            key = rule.target_field
            val = self._resolve_value(context, key, extra_scope)

            # 2. Evaluate
            try:
                context_key = f"{process_name}:{key}"
                self.policy.evaluate(rule, val, context_key)
            except AuditInterlockError as e:
                # Re-raise to be caught by Engine
                raise e

    def _resolve_value(self, context: Any, path: str, extra_scope: Dict[str, Any] = None):
        """
        Resolves a dot-notation path, checking input_args first, then context.
        """
        # 1. Check extra_scope (simple key match, e.g. 'agent_id')
        if extra_scope and path in extra_scope:
            return extra_scope[path]
        
        # 2. Check context recursive (e.g. 'domain.user.age')
        return self._getattr_recursive(context, path)

    def _getattr_recursive(self, obj, path: str):
        """Helper to get 'domain.user.age' from context object."""
        try:
            parts = path.split('.')
            curr = obj
            for p in parts:
                curr = getattr(curr, p)
            return curr
        except AttributeError:
             return None # Field missing
