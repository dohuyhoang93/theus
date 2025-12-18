import os
from typing import Dict, Callable, Any, Optional
import logging
import yaml
from contextlib import contextmanager
from .context import BaseSystemContext
from .contracts import ProcessContract, ContractViolationError
from .guards import ContextGuard
from .delta import Transaction
from .locks import LockManager
from .audit import ContextAuditor, AuditInterlockError
from .config import AuditRecipe

logger = logging.getLogger("POPEngine")

from .interfaces import IEngine

class POPEngine(IEngine):
    def __init__(self, system_ctx: BaseSystemContext, strict_mode: Optional[bool] = None, audit_recipe: Optional[AuditRecipe] = None):
        self.ctx = system_ctx
        self.process_registry: Dict[str, Callable] = {}
        
        # Initialize Audit System (Industrial V2)
        recipes = audit_recipe.definitions if audit_recipe else {}
        self.auditor = ContextAuditor(recipes)

        # Resolve Strict Mode Logic
        if strict_mode is None:
            # Theus (New) > POP (Legacy) > Default "0"
            env_val = os.environ.get("THEUS_STRICT_MODE", os.environ.get("POP_STRICT_MODE", "0")).lower()
            strict_mode = env_val in ("1", "true", "yes", "on")
        
        self.lock_manager = LockManager(strict_mode=strict_mode)
        
        # Attach Lock to Contexts
        if hasattr(self.ctx, 'set_lock_manager'):
            self.ctx.set_lock_manager(self.lock_manager)
            
        if hasattr(self.ctx.global_ctx, 'set_lock_manager'):
            self.ctx.global_ctx.set_lock_manager(self.lock_manager)
            
        if hasattr(self.ctx.domain_ctx, 'set_lock_manager'):
            self.ctx.domain_ctx.set_lock_manager(self.lock_manager)

    def register_process(self, name: str, func: Callable):
        if not hasattr(func, '_pop_contract'):
            logger.warning(f"Process {name} does not have a contract decorator (@process). Safety checks disabled.")
        self.process_registry[name] = func

    def get_process(self, name: str) -> Callable:
        return self.process_registry.get(name)

    def execute_process(self, process_name: str, context: Any = None) -> Any:
        """
        Implementation of IEngine.execute_process.
        """
        # POPEngine is stateful (holds self.ctx).
        return self.run_process(process_name)

    def run_process(self, name: str, **kwargs):
        """
        Thực thi một process theo tên đăng ký.
        """
        if name not in self.process_registry:
            raise KeyError(f"Process '{name}' not found in registry.")
        
        func = self.process_registry[name]
        
        # --- INPUT GATE (FDC/RMS Check) ---
        # Industrial Audit V2: Check inputs (Phase 1)
        try:
            if self.auditor:
                self.auditor.audit_input(name, self.ctx, input_args=kwargs)
        except AuditInterlockError as e:
            logger.critical(f"🛑 [INPUT GAGTE] Process '{name}' blocked by Audit Interlock: {e}")
            raise # Stop immediately

        # UNLOCK CONTEXT for Process execution
        with self.lock_manager.unlock():
            if hasattr(func, '_pop_contract'):
                contract: ProcessContract = func._pop_contract
                allowed_inputs = set(contract.inputs)
                allowed_outputs = set(contract.outputs)
                
                tx = Transaction(self.ctx)
                guarded_ctx = ContextGuard(self.ctx, allowed_inputs, allowed_outputs, transaction=tx)
                
                try:
                    result = func(guarded_ctx, **kwargs)
                    tx.commit()
                    
                    # --- OUTPUT GATE (Quality Check) ---
                    # Industrial Audit V2: Check outputs AFTER commit
                    # Note: We check the committed data in self.ctx
                    try:
                        self.auditor.audit_output(name, self.ctx)
                    except AuditInterlockError as e:
                        # Serious failure implies production defect.
                        # What to do? Rollback is impossible (tx committed).
                        # We must Raise & Halt workflow.
                        logger.critical(f"🛑 [OUTPUT GATE] Process '{name}' produced Defective Output: {e}")
                        raise

                    return result
                    
                except Exception as e:
                    tx.rollback()
                    if isinstance(e, (ContractViolationError, AuditInterlockError)):
                         raise e
                    
                    error_name = type(e).__name__
                    if error_name not in contract.errors:
                        raise ContractViolationError(
                            f"Undeclared Error Violation: Process '{name}' raised '{error_name}'."
                        ) from e
                    raise e
            else:
                return func(self.ctx, **kwargs)

    def execute_workflow(self, workflow_path: str, **kwargs):
        """
        Thực thi Workflow YAML.
        """
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow_def = yaml.safe_load(f) or {}
            
        steps = workflow_def.get('steps', [])
        logger.info(f"▶️ Starting Workflow: {workflow_path} ({len(steps)} steps)")

        for step in steps:
            if isinstance(step, str):
                self.run_process(step, **kwargs)
            elif isinstance(step, dict):
                process_name = step.get('process')
                if process_name:
                    self.run_process(process_name, **kwargs)
        
        return self.ctx

    @contextmanager
    def edit(self):
        """
        Safe Zone for external mutation.
        """
        with self.lock_manager.unlock():
            yield self.ctx


