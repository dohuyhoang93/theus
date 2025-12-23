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
from .audit import ContextAuditor, AuditInterlockError, AuditBlockError
from .config import AuditRecipe

logger = logging.getLogger("TheusEngine")

from .interfaces import IEngine

class TheusEngine(IEngine):
    """
    Theus Kernel (formerly POPEngine).
    Manages Safety, Governance, and Orchestration for Process-Oriented Programming.
    """
    def __init__(self, system_ctx: BaseSystemContext, strict_mode: Optional[bool] = None, audit_recipe: Optional[AuditRecipe] = None):
        self.ctx = system_ctx
        self.process_registry: Dict[str, Callable] = {}
        self.workflow_cache: Dict[str, Any] = {} # Cache for parsed YAML workflows
        
        # Initialize Audit System (Industrial V2)
        # BUGFIX: ContextAuditor expects AuditRecipe obj, not dict
        self.auditor = ContextAuditor(audit_recipe) if audit_recipe else None

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

    def scan_and_register(self, package_path: str):
        """
        Auto-Discovery: Scans directory for modules and registers @process functions.
        """
        import importlib.util
        import inspect

        logger.info(f"🔎 Scanning for processes in: {package_path}")
        
        for root, dirs, files in os.walk(package_path):
            if "__pycache__" in root: continue
            
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    module_path = os.path.join(root, file)
                    spec = importlib.util.spec_from_file_location(file[:-3], module_path)
                    if spec and spec.loader:
                        try:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            
                            # Scan module for decorated functions
                            for name, obj in inspect.getmembers(module):
                                if inspect.isfunction(obj) and hasattr(obj, '_pop_contract'):
                                    # Use function name as register name
                                    # Suggestion: Support alias in decorator later
                                    logger.info(f"   + Found Process: {name}")
                                    self.register_process(name, obj)
                                    
                        except Exception as e:
                            logger.error(f"Failed to load module {file}: {e}")


    def get_process(self, name: str) -> Callable:
        return self.process_registry.get(name)

    def execute_process(self, process_name: str, context: Any = None) -> Any:
        """
        Implementation of IEngine.execute_process.
        """
        # Engine is stateful (holds self.ctx).
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
                guarded_ctx = ContextGuard(
                    self.ctx, 
                    allowed_inputs, 
                    allowed_outputs, 
                    transaction=tx, 
                    strict_mode=self.lock_manager.strict_mode,
                    process_name=name # <--- Inject Process Name here
                )
                
                try:
                    result = func(guarded_ctx, **kwargs)

                    # --- OUTPUT GATE (Quality Check) ---
                    # MOVED: Check BEFORE Commit to allow safe Rollback (Shadow Audit).
                    # We pass 'guarded_ctx' so Auditor sees the uncommitted mutations.
                    if self.auditor:
                        try:
                            self.auditor.audit_output(name, guarded_ctx)
                        except AuditInterlockError as e:
                            logger.critical(f"🛑 [OUTPUT GATE] Process '{name}' blocked: {e}")
                            raise # Will trigger Rollback in outer block

                    # Everything OK -> Commit
                    tx.commit()

                    return result
                    
                except Exception as e:
                    tx.rollback()
                    # Pop Audit Exceptions should just propagate (after rollback)
                    if isinstance(e, (ContractViolationError, AuditInterlockError, AuditBlockError)):
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
        if workflow_path in self.workflow_cache:
            workflow_def = self.workflow_cache[workflow_path]
        else:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_def = yaml.safe_load(f) or {}
            self.workflow_cache[workflow_path] = workflow_def
            logger.info(f"Loaded and cached workflow: {workflow_path}")
            
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

# Backward compatibility (Deprecated)
class POPEngine(TheusEngine):
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn("POPEngine is deprecated. Use TheusEngine instead.", DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)


