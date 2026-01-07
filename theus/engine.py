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

try:
    import theus_core
    from theus_core import Engine as RustEngine
except ImportError as e:
    import warnings
    print(f"DEBUG IMPORT ERROR: {e}")
    warnings.warn("Theus Rust Core not found. Using Mock.", RuntimeWarning)
    class RustEngine:
        def __init__(self, ctx): pass
        def execute_process(self, name): raise NotImplementedError("Rust Extension Missing. Please compile with `maturin develop`.")
        def register_process(self, name, func): pass

class TheusEngine(RustEngine, IEngine):
    """
    Theus Kernel (Rust Accelerated).
    Manages Safety, Governance, and Orchestration for Process-Oriented Programming.
    
    .. deprecated:: 0.2.0
       Core logic moved to Rust. This class is now a thin wrapper around `theus_core.Engine`.
    """
    def __init__(self, system_ctx: BaseSystemContext, strict_mode: Optional[bool] = None, audit_recipe: Optional[AuditRecipe] = None):
        # super().__init__(system_ctx) # Init Rust Engine handled by __new__
        self.ctx = system_ctx
        # self.process_registry: Dict[str, Callable] = {} # Rust manages this now
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

        # Flux Counters
        self._flux_ops_count = 0
        self._flux_max_ops = int(os.environ.get("THEUS_MAX_LOOPS", 10000))

    def register_process(self, name: str, func: Callable):
        if not hasattr(func, '_pop_contract'):
            logger.warning(f"Process {name} does not have a contract decorator (@process). Safety checks disabled.")
        # Delegate to Rust
        super().register_process(name, func)

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
                            logger.error(f"❌ [TheusEngine] Failed to load module {file}: {e}")
                            import traceback
                            traceback.print_exc() # Ensure visibility in console


    def get_process(self, name: str) -> Callable:
        return self.process_registry.get(name)

    def execute_process(self, process_name: str, **kwargs) -> Any:
        # Implementation of IEngine.execute_process.
        # Delegates to Rust Core.
        return super().execute_process(process_name, **kwargs)

    def run_process(self, name: str, **kwargs):
        # Alias for execute_process to support old calls or internal calls
        return self.execute_process(name, **kwargs)

    def execute_workflow(self, workflow_path: str, **kwargs):
        """
        Thực thi Workflow YAML (Flux Enhanced).
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

        # Delegate to Rust Flux Engine
        # Rust handles recursion, control flow, and safety limits
        logger.info(f"🔄 [THEUS-RUST-BRIDGE] Delegating execution of {len(steps)} steps to internal Rust Engine 🦀")
        super().execute_workflow(steps, **kwargs)
        
        return self.ctx

    def _execute_step(self, step: Any, **kwargs):
        """
        Recursive Step Executor for Flux.
        """
        self._flux_ops_count += 1
        if self._flux_ops_count > self._flux_max_ops:
            raise RuntimeError(f"🚨 Flux Safety Trip: Exceeded {self._flux_max_ops} operations. Check for infinite loops.")

        # Case 1: Simple String (Process Name)
        if isinstance(step, str):
            self.run_process(step, **kwargs)
            return

        # Case 2: Dictionary (Process or Flux Command)
        if isinstance(step, dict):
            # 2.1 Standard Process
            if 'process' in step:
                self.run_process(step['process'], **kwargs)
                return

            # 2.2 Flux: If / Else
            if step.get('flux') == 'if':
                condition = step.get('condition', 'False')
                if self._resolve_condition(condition):
                    # Then branch
                    for child in step.get('then', []):
                        self._execute_step(child, **kwargs)
                else:
                    # Else branch
                    for child in step.get('else', []):
                        self._execute_step(child, **kwargs)
                return

            # 2.3 Flux: While
            if step.get('flux') == 'while':
                condition = step.get('condition', 'False')
                # Loop safety is handled by global _flux_ops_count
                while self._resolve_condition(condition):
                    for child in step.get('do', []):
                        self._execute_step(child, **kwargs)
                return

            # 2.4 Flux: Run (Nested steps wrapper)
            if step.get('flux') == 'run':
                for child in step.get('steps', []):
                    self._execute_step(child, **kwargs)
                return
                
        # Fallback
        logger.warning(f"⚠️ Unknown step format skipped: {step}")

    def _resolve_condition(self, condition_str: str) -> bool:
        """
        Safe(r) Condition Evaluator.
        Allows access to 'ctx', 'domain', 'global', 'system'.
        """
        # Prepare restricted locals
        safe_locals = {
            'ctx': self.ctx,
            'domain': getattr(self.ctx, 'domain_ctx', None),
            'global': getattr(self.ctx, 'global_ctx', None),
            'system': getattr(self.ctx, 'system_ctx', None),
            'len': len,
            'int': int,
            'float': float,
            'str': str, 
            'bool': bool
        }
        
        # Also inject aliases if strict hierarchy not followed
        if hasattr(self.ctx, 'global_ctx'):
             safe_locals['global_ctx'] = self.ctx.global_ctx
        if hasattr(self.ctx, 'domain_ctx'):
             safe_locals['domain_ctx'] = self.ctx.domain_ctx

        try:
            # We use eval() but strictly limited logic should be in condition strings.
            # Ideally, use a safer parser like simpleeval in V2.1.
            # For now, we trust the Orchestrator YAML author (Dev/Ops).
            return bool(eval(str(condition_str), {"__builtins__": {}}, safe_locals))
        except Exception as e:
            logger.error(f"❌ Condition Evaluation Failed: '{condition_str}' -> {e}")
            return False

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


