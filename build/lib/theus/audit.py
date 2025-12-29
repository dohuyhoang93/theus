import time
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from .config import RuleSpec, ProcessRecipe, AuditRecipe

logger = logging.getLogger("POP_AUDIT")

class AuditError(Exception):
    """Base for audit failures."""
    pass

class AuditInterlockError(AuditError):
    """Level S/A violation -> Hard Crash (Stop Workflow)."""
    pass

class AuditBlockError(AuditError):
    """Level B violation -> Soft Block (Rollback Transaction)."""
    pass

@dataclass
class ViolationRecord:
    process_name: str
    rule: RuleSpec
    actual_value: Any
    timestamp: float

class AuditTracker:
    """Tracks violations and counters with auto-reset policy."""
    def __init__(self):
        self.violations: Dict[str, List[ViolationRecord]] = {}
        self.counters: Dict[str, int] = {} # Key: "process_name:field:condition"

    def record_violation(self, process_name: str, rule: RuleSpec, value: Any) -> int:
        key = self._get_key(process_name, rule)
        self.counters[key] = self.counters.get(key, 0) + 1
        
        rec = ViolationRecord(process_name, rule, value, time.time())
        if process_name not in self.violations:
            self.violations[process_name] = []
        self.violations[process_name].append(rec)
        
        return self.counters[key]

    def reset_counter(self, process_name: str, rule: RuleSpec):
        """Reset counter to 0 (Used when Threshold is hit)."""
        key = self._get_key(process_name, rule)
        if key in self.counters:
            self.counters[key] = 0

    def _get_key(self, process_name: str, rule: RuleSpec) -> str:
        return f"{process_name}:{rule.target_field}:{rule.condition}"

class AuditPolicy:
    """Evaluates Rules against Context Data."""
    def __init__(self, recipe: AuditRecipe):
        self.recipe = recipe
        self.tracker = AuditTracker()

    def evaluate(self, process_name: str, stage: str, ctx: Any, extra_data: Dict = None):
        if not self.recipe: return
        
        proc_def = self.recipe.definitions.get(process_name)
        if not proc_def: return

        # Select Rules based on Stage (Input Gate vs Output Gate)
        rules = proc_def.input_rules if stage == 'input' else proc_def.output_rules
        
        for rule in rules:
            try:
                # 1. Resolve Value (Support Computed Paths e.g. tensor.mean())
                actual_val = self._resolve_value(ctx, rule.target_field, extra_data)
                
                # 2. Check Condition
                if not self._check_condition(actual_val, rule.condition, rule.value):
                    # Violation!
                    count = self.tracker.record_violation(process_name, rule, actual_val)
                    self._handle_violation(process_name, rule, actual_val, count, stage)
                else:
                    # Success -> Check policy to Reset
                    if rule.reset_on_success:
                        self.tracker.reset_counter(process_name, rule)
                
            except AttributeError:
                pass
            except AuditError as ae:
                 # Re-raise critical audit failures so Engine can handle them
                 raise ae
            except Exception as e:
                logger.error(f"Audit Error checking {rule.target_field}: {e}")

    def _handle_violation(self, process_name, rule, value, count, stage):
        msg = f"[{stage.upper()} GATE] Rule '{rule.condition}' violated on '{rule.target_field}'. Value={value}, Limit={rule.value}. (Count: {count})"
        if rule.message:
            msg = f"{msg} | Reason: {rule.message}"
        
        # Dual Threshold Logic
        
        # 1. MAX THRESHOLD -> CRITICAL ACTION
        if count >= rule.max_threshold:
            # TRIGGERED! -> RESET COUNTER (Start new cycle)
            self.tracker.reset_counter(process_name, rule)
            
            if rule.level == 'S': # Safety Critical
                raise AuditInterlockError(f"🛑 [SAFETY INTERLOCK] {msg}")
            
            elif rule.level == 'A': # Abort (Crash)
                raise AuditInterlockError(f"🛑 [LEVEL A ABORT] {msg}")
                
            elif rule.level == 'B': # Block (Soft Fail)
                raise AuditBlockError(f"⚠️ [LEVEL B BLOCK] {msg}")
                
            elif rule.level == 'C': # Campaign/Warning
                logger.warning(f"⚠️ [LEVEL C WARN] {msg} (Cycle Reset)")

        # 2. MIN THRESHOLD -> EARLY WARNING
        elif count >= rule.min_threshold:
             logger.warning(f"🟡 [EARLY WARNING] {msg}")

    def _check_condition(self, actual, cond, limit) -> bool:
        if cond == 'min': return actual >= limit
        if cond == 'max': return actual <= limit
        if cond == 'eq': return actual == limit
        if cond == 'neq': return actual != limit
        
        # Phase 2: Length Checks (Smart Audit)
        if cond == 'max_len': return len(actual) <= limit
        if cond == 'min_len': return len(actual) >= limit
        
        # Add regex/custom validators here
        return True

    def _resolve_value(self, ctx: Any, path: str, extra_data: Dict = None) -> Any:
        # 1. Check extra_data (e.g. kwargs)
        if extra_data and path in extra_data:
            return extra_data[path]

        # 2. Check Context (Support "domain.tensor.mean()")
        parts = path.split('.')
        current = ctx
        for p in parts:
            # Handle Method Call if syntax is "name()"
            if p.endswith('()'):
                method_name = p[:-2]
                if isinstance(current, dict):
                     # Rare case: dict has method? (e.g. keys(), values())
                     # Or user meant accessing key "name()"? Assuming method call on dict object
                     current = getattr(current, method_name)()
                else:
                     current = getattr(current, method_name)()
            else:
                # Handle Attribute vs Dict Key
                if isinstance(current, dict):
                    # Support "tensors.traces" -> tensors['traces']
                    try:
                        current = current[p]
                    except KeyError:
                         # Fallback: maybe it's a dict method like 'get'? 
                         # But 'get' is attribute. 
                         # If key missing, we can't resolve.
                         raise AttributeError(f"Key '{p}' not found in dict path '{path}'")
                else:
                    current = getattr(current, p)
        return current

class ContextAuditor:
    """Middleware injected into Engine to bridge Policy and Runtime."""
    def __init__(self, recipe: AuditRecipe):
        self.policy = AuditPolicy(recipe)

    def audit_input(self, process_name: str, ctx: Any, input_args: Dict = None):
        if self.policy:
            self.policy.evaluate(process_name, 'input', ctx, extra_data=input_args)

    def audit_output(self, process_name: str, ctx: Any):
        if self.policy:
            self.policy.evaluate(process_name, 'output', ctx)
