import os
import sys
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union, Callable

# Load Core Rust Module
try:
    import theus_core
    from theus.structures import StateUpdate, FunctionResult
    _HAS_RUST_CORE = True
except ImportError as e:
    _HAS_RUST_CORE = False
    print(f"WARNING: 'theus_core' not found. Reason: {e}")
    print("Running in Pure Python Fallback (Slower).")

from theus.context import BaseSystemContext, TransactionError
from theus.contracts import SemanticType, ContractViolationError
SecurityViolationError = ContractViolationError

class TheusEngine:
    """
    Theus v3.0 Main Engine.
    Orchestrates Context, Processes, and Rust Core Transaction Manager.
    
    Args:
        context: Initial context data (optional)
        strict_mode: Enable strict contract enforcement (default: True)
        strict_cas: Enable Strict CAS mode (default: False)
            - False (default): Use Rust Smart CAS with Key-Level conflict detection
              Allows updates when specific keys haven't changed, even if version differs.
            - True: Use Strict CAS - reject ALL version mismatches regardless of keys.
        audit_recipe: Audit configuration (optional)
    """
    def __init__(self, context=None, strict_mode=True, strict_cas=False, audit_recipe=None):
        self._context = context  
        self._registry = {}     
        self._strict_mode = strict_mode
        self._strict_cas = strict_cas  # v3.0.4: CAS mode control
        self._audit = None       
        
        # Load Audit Config if available
        # v3.0.2: Standardized ConfigFactory Usage (Arg > File)
        audit_config = audit_recipe
        if not audit_config:
            from theus.config import ConfigFactory
            audit_config = ConfigFactory.load_audit_recipe()

        if audit_config:
            # Unwrap AuditRecipeBook if necessary
            if hasattr(audit_config, 'rust_recipe'):
                audit_config = audit_config.rust_recipe

            from theus.audit import AuditSystem
            self._audit = AuditSystem(audit_config)

        # Initialize Rust Core (Microkernel)
        if _HAS_RUST_CORE:
            # Rust takes ownership of the Data Zone
            init_data = context.to_dict() if context else {}
            self._core = theus_core.TheusEngine() # No args
            
            # Hydrate state via CAS (Version 0 -> Init)
            if init_data:
                try:
                    # Version 0 is start.
                    self._core.compare_and_swap(0, init_data)
                except Exception as e:
                    print(f"WARNING: Initial hydration failed: {e}")
            
            # v3.1: Heavy Asset Manager (Shared Memory)
            try:
                from theus.structures import ManagedAllocator
                self._allocator = ManagedAllocator(
                     capacity_mb=int(os.environ.get("THEUS_HEAP_SIZE", 512))
                )
            except Exception as e:
                 print(f"WARNING: ManagedAllocator init failed: {e}")
                 self._allocator = None
        else:
            raise RuntimeError("Theus v3.0 requires Rust Core!")

    def _create_restricted_view(self, ctx):
        """Create a Read-Only Proxy for Pure Processes."""
        # Use Rust Core to generate a safe View
        # v2.2 legacy: Python proxy
        # v3.0: Rust wrapper
        return RestrictedStateProxy(self._core.state)

    def scan_and_register(self, path):
        import os
        import importlib.util
        
        if not os.path.isdir(path):
            return
            
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    file_path = os.path.join(root, file)
                    module_name = os.path.splitext(file)[0]
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        try:
                            spec.loader.exec_module(module)
                            # Inspect for @process decorated functions
                            for name, obj in vars(module).items():
                                if callable(obj) and hasattr(obj, "_pop_contract"):
                                    self.register(obj)
                        except Exception as e:
                            print(f"Failed to load module {file}: {e}")

    def execute_workflow(self, yaml_path, **kwargs):
        """Execute Workflow YAML using Rust Flux DSL Engine."""
        from theus_core import WorkflowEngine
        import os
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        
        max_ops = int(os.environ.get("THEUS_MAX_LOOPS", 10000))
        debug = os.environ.get("THEUS_FLUX_DEBUG", "0").lower() in ("1", "true", "yes")
        
        wf_engine = WorkflowEngine(yaml_content, max_ops, debug)
        
        # Build context dict for condition evaluation
        data = self.state.data
        
        # v3.3: Inject Signal Snapshot (Fix Binding Blindness)
        # We need to expose transient signals to the Flux condition evaluator
        signals = {}
        if hasattr(self.state, "signals"):
             signals = self.state.signals
             
        ctx = {
            'domain': data.get('domain', None),
            'global': data.get('global', None),
            'signal': signals,
            'cmd': signals # Alias for convenience
        }
        
        # Execute workflow with process executor callback
        executed = wf_engine.execute(ctx, self._run_process_sync)
        
        return executed
    
    def _run_process_sync(self, name: str, **kwargs):
        """Run a process synchronously (blocking). Called by Rust Flux Engine."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
             # Blocking call from Rust, but loop is running (likely we are in a thread)
             # Schedule coroutine and wait for result safely
             future = asyncio.run_coroutine_threadsafe(self.execute(name, **kwargs), loop)
             return future.result()
        else:
            loop.run_until_complete(self.execute(name, **kwargs))

    @property
    def state(self):
        return self._core.state
        
    @property
    def heavy(self):
        """v3.1 Managed Memory Allocator"""
        return self._allocator

    def transaction(self):
        return self._core.transaction()
        
    def compare_and_swap(self, expected_version, data=None, heavy=None, signal=None):
        """
        Compare-And-Swap with configurable conflict detection.
        
        Behavior depends on `strict_cas` setting:
        - strict_cas=False (default): Rust Smart CAS with Key-Level detection.
          Allows merge when specific keys haven't changed since expected_version.
        - strict_cas=True: Strict mode - rejects ALL version mismatches.
        
        Returns:
            None on success, State object on failure (strict mode), 
            or raises ContextError on conflict (smart mode).
        """
        # Strict CAS Mode: Pre-flight Check (Python Side)
        if self._strict_cas:
            current_version = self.state.version
            if current_version != expected_version:
                return self.state  # Gentle rejection
        
        # Delegate to Rust Core (Smart CAS with Key-Level detection)
        return self._core.compare_and_swap(expected_version, data=data, heavy=heavy, signal=signal)

    def register(self, func):
        """
        Registers a process and validates its contract.
        """
        contract = getattr(func, "_pop_contract", None)
        if contract:
            # Semantic Firewall: Registration Check
            if contract.semantic == SemanticType.PURE:
                for inp in contract.inputs:
                    if inp.startswith("signal.") or inp.startswith("meta."):
                        raise ContractViolationError(f"Pure process cannot take inputs from Zone: Signal/Meta (Found: {inp})")
        
        self._registry[func.__name__] = func

    async def execute(self, func_or_name, *args, **kwargs):
        """
        Executes a process and handles Transactional Commit logic and Safety Guard enforcement.
        Extended v3.3: Supports Automatic Retry (Backoff) for Conflict Resolution.
        """
        import asyncio
        
        # Resolve function
        if isinstance(func_or_name, str):
            func = self._registry.get(func_or_name)
            if not func:
                raise ValueError(f"Process '{func_or_name}' not found in registry")
        else:
            func = func_or_name

        # Helper for Loop
        start_version = None
        
        while True:
            try:
                result = await self._attempt_execute(func, *args, **kwargs)
                
                # If success, clear conflict counter
                if hasattr(self._core, "report_success"):
                    self._core.report_success(func.__name__)
                
                return result
                
            except Exception as e:
                # Check for CAS Conflict (ContextError)
                err_msg = str(e)
                is_cas_error = "CAS Version Mismatch" in err_msg
                is_busy_error = "System Busy" in err_msg
                
                if is_busy_error:
                     # VIP Active. Sleep and retry.
                     # print(f"[*] System Busy (VIP). Waiting...")
                     await asyncio.sleep(0.05)
                     continue

                if is_cas_error and hasattr(self._core, "report_conflict"):
                     decision = self._core.report_conflict(func.__name__)
                     if decision.should_retry:
                         print(f"[*] Conflict detected for {func.__name__}. Retrying in {decision.wait_ms}ms...")
                         await asyncio.sleep(decision.wait_ms / 1000.0)
                         continue
                
                # If not retryable or other error, propagate
                raise e

    async def _attempt_execute(self, func, *args, **kwargs):
        contract = getattr(func, "_pop_contract", None)
        
        # v3.0.2: Auto-Dispatch Parallel Processes
        if contract and contract.parallel:
             import asyncio
             loop = asyncio.get_running_loop()
             return await loop.run_in_executor(None, lambda: self.execute_parallel(func.__name__, **kwargs))

        # Transaction Management (v3.1 Explicit Lifecycle)
        # We implicitly create a transaction scope for the execution.
        start_version = self.state.version
        tx = theus_core.Transaction(self._core)
        
        target_func = func  
        if contract and contract.semantic == SemanticType.PURE:
             # Pure Wrapper Logic + Arg Capture
             # [v3.0.4] Pass contract.inputs to create filtered restricted view
             allowed_inputs = contract.inputs if contract else []
             import inspect
             if inspect.iscoroutinefunction(func):
                  async def safe_wrapper(ctx, *_, **__):
                       restricted = self._create_restricted_view(ctx, allowed_paths=allowed_inputs)
                       return await func(restricted, *args, **kwargs)
                  safe_wrapper.__name__ = func.__name__
                  target_func = safe_wrapper
             else:
                  def safe_wrapper(ctx, *_, **__):
                       restricted = self._create_restricted_view(ctx, allowed_paths=allowed_inputs)
                       return func(restricted, *args, **kwargs)
                  safe_wrapper.__name__ = func.__name__
                  target_func = safe_wrapper
        else:
             # If not PURE (no restricted view needed), we still need to bind arguments!
             import inspect
             if inspect.iscoroutinefunction(func):
                  async def arg_binder(ctx, *_, **__):
                       # v3.1 Guard Wrapping (Admin Mode for Non-Pure)
                       # Allows full access but enables SupervisorProxy for nested dicts
                       # INJECT TRANSACTION:
                       guard = theus_core.ContextGuard(ctx, [], [], None, tx, True, False)
                       return await func(guard, *args, **kwargs)
                  arg_binder.__name__ = func.__name__
                  target_func = arg_binder
             else:
                  def arg_binder(ctx, *_, **__):
                       # v3.1 Guard Wrapping (Admin Mode for Non-Pure)
                       guard = theus_core.ContextGuard(ctx, [], [], None, tx, True, False)
                       return func(guard, *args, **kwargs)
                  arg_binder.__name__ = func.__name__
                  target_func = arg_binder

        # Run via Rust Core (Handles Audit, Timing, etc)
        try:
             result = await self._core.execute_process_async(func.__name__, target_func)
             
             # v3.1 Explicit Commit (Supervisor Mode)
             # Verify state version to ensure Optimistic Concurrency Control
             # current_ver = self.state.version (Already captured as start_version)
             
             # Commit pending changes from Transaction
             self._core.compare_and_swap(start_version, data=tx.pending_data, heavy=tx.pending_heavy, signal=tx.pending_signal)

             if self._audit:
                  self._audit.log_success(func.__name__)
             
        except Exception as e:
            if self._audit:
                try:
                    self._audit.log_fail(key=func.__name__)
                except Exception as audit_exc:
                     raise audit_exc from e
            raise e
            

        
        # Logic for Output Mapping
        # 1. StateUpdate (Explicit)
        if StateUpdate and isinstance(result, StateUpdate):
            if contract:
                self._check_output_permission(result, contract)
            
            expected = result.assert_version
            if expected is not None:
                data = result.data or {}
                if result.key is not None:
                    data[result.key] = result.val
                
                self._core.compare_and_swap(expected, data, result.heavy, result.signal)
            return result
        
        # 2. POP Output Mapping (Implicit)
        elif contract and contract.outputs:
            outputs = contract.outputs
            
            # Decide how to unpack result
            if isinstance(result, dict):
                # [v3.1 Fix] ambiguity: Is dict a Map or a Value?
                # Check if result keys match output names
                is_map = any(out_key in result for out_key in outputs)
                
                if is_map:
                    vals = []
                    for out_key in outputs:
                        if out_key in result:
                            vals.append(result[out_key])
                        else:
                            vals.append(None)
                elif len(outputs) == 1:
                     # Treat as Value
                     vals = (result,)
                else:
                     # Heuristic failed, assume Map (strict)
                     vals = [result.get(k) for k in outputs]
            else:
                 # Tuple/List Return (Positional)
                 vals = result if len(outputs) > 1 else (result,)
                 if len(outputs) == 1 and not isinstance(result, tuple):
                      vals = (result,)
        
            updates_by_root = {} 
            new_heavy = {}
            
            for path, val in zip(outputs, vals):
                parts = path.split('.')
                root = parts[0]
                rest = parts[1:]
                
                if root in ["heavy"]:
                    if len(rest) > 0:
                        new_heavy[rest[0]] = val
                elif root in ["domain", "global", "global_"]:
                     key = "global" if root == "global_" else root
                     if key not in updates_by_root:
                         # Fetch current safely
                         curr_wrapper = getattr(self.state, key, None)
                         print(f"DEBUG_MAP: Fetching key='{key}' wrapper_type={type(curr_wrapper)}")
                         if hasattr(curr_wrapper, "to_dict"):
                               updates_by_root[key] = curr_wrapper.to_dict()
                               print(f"DEBUG_MAP: Converted '{key}' to dict via to_dict()")
                         elif isinstance(curr_wrapper, dict):
                               updates_by_root[key] = curr_wrapper.copy()
                         else:
                               # Preserve Object Identity/State for Pydantic/Dataclasses
                               updates_by_root[key] = curr_wrapper
                     
                     if len(rest) > 0:
                         target = updates_by_root[key]
                         field = rest[0]
                         if isinstance(target, dict):
                             target[field] = val
                         else:
                             # Object Mutation
                             setattr(target, field, val)
            
            if start_version is not None:
                 final_heavy = new_heavy if new_heavy else None
                 print(f"DEBUG: Attempting CAS for {func.__name__} version {start_version} updates: {updates_by_root.keys()}")
                 res = self._core.compare_and_swap(start_version, updates_by_root, final_heavy, None, func.__name__)
                 print(f"DEBUG: CAS Result for {func.__name__}: {res}")
            else:
                 print(f"DEBUG: CAS Skipped for {func.__name__} (start_version is None)")

            return result
        
        return result
    
    def _create_restricted_view(self, ctx, allowed_paths=None):
        # [v3.0.4] Create a restricted view with input filtering
        # The Proxy ensures AttributeError/ContractViolationError on unauthorized access
        return RestrictedStateProxy(ctx.restrict_view(), allowed_paths=allowed_paths)
        
    def _check_output_permission(self, update, contract):
        # Check if update keys match contract.outputs glob patterns
        # Simple glob match
        import fnmatch
        
        keys_to_check = []
        if update.key:
             # Heuristic: if key is dotted path e.g. "domain.system.config"
             keys_to_check.append(update.key)
        
        if update.data:
             for k in update.data.keys():
                 keys_to_check.append(f"data.{k}") 
        
        valid_patterns = contract.outputs
        
        for key in keys_to_check:
             # Normalization
             check_key = key
             if key.startswith("data."):
                 check_key = key[5:]
             
             allowed = False
             for pattern in valid_patterns:
                 if fnmatch.fnmatch(check_key, pattern):
                     allowed = True
                     break
             
             if not allowed:
                  raise PermissionError(f"Write permission denied for path '{check_key}'")

    @contextmanager
    def edit(self):
        """
        Safe Zone for external mutation (v3.0.5 compliant).
        Yields the SystemContext for direct modification, then syncs to Rust Core.
        
        Usage:
            with engine.edit() as ctx:
                ctx.domain.counter = 999
        """
        # 1. Yield the Context (not self)
        yield self._context
        
        # 2. Sync back to Rust Core (Blind Update with current version)
        # This emulates a forced 'Batch Transaction'
        if hasattr(self, '_core'):
             try:
                 # We only sync 'domain' and 'global' from context
                 # This is expensive (serialization) but safe for testing
                 current_ver = 0
                 try:
                      current_ver = self.state.version
                 except:
                      pass
                      
                 # Construct update payload
                 # Note: self._context.to_dict() should return {'domain': ..., 'global': ...}
                 # But we need to check if to_dict exists
                 updates = {}
                 if hasattr(self._context, 'to_dict'):
                      updates = self._context.to_dict()
                 elif hasattr(self._context, 'domain'):
                       # Manual extraction for BaseSystemContext
                       if hasattr(self._context.domain, 'to_dict'):
                            updates['domain'] = self._context.domain.to_dict()
                       else:
                            updates['domain'] = self._context.domain.__dict__
                 
                 # Force Push
                 self._core.compare_and_swap(current_ver, updates)
                 
             except Exception as e:
                 print(f"WARNING: engine.edit() failed to sync to Rust Core: {e}")

    def execute_parallel(self, process_name, **kwargs):
        """
        Execute a process in parallel pool (Sub-Interpreter or Process).
        
        Uses `THEUS_USE_PROCESSES=1` env var to force ProcessPool (for NumPy compatibility).
        Uses `THEUS_POOL_SIZE=N` env var to set pool size (default: 4).
        
        Args:
            process_name: Name of the registered process to execute.
            **kwargs: Arguments to pass to the process (merged into ctx.domain).
            
        Returns:
            Result from the process execution.
        """
        from theus.parallel import ProcessPool, ParallelContext
        import os
        
        use_processes = os.environ.get("THEUS_USE_PROCESSES", "0") == "1"
        pool_size = int(os.environ.get("THEUS_POOL_SIZE", "4"))
        
        # Create pool lazily (cached on engine instance)
        if not hasattr(self, '_parallel_pool') or self._parallel_pool is None:
            if use_processes:
                self._parallel_pool = ProcessPool(size=pool_size)
            else:
                try:
                    from theus.parallel import InterpreterPool
                    self._parallel_pool = InterpreterPool(size=pool_size)
                except Exception as e:
                    print(f"WARNING: Sub-Interpreters not available ({e}), falling back to ProcessPool.")
                    self._parallel_pool = ProcessPool(size=pool_size)
        
        # Get registered function
        func = self._registry.get(process_name)
        if not func:
            raise ValueError(f"Process '{process_name}' not found in registry")
        
        # Create ParallelContext with domain kwargs
        # NOTE: We don't pass heavy zone directly (FrozenDict is not picklable).
        # Workers should access shared memory via engine.heavy.get() with descriptor metadata.
        ctx = ParallelContext(domain=kwargs, heavy=None)
        
        # Submit and wait for result
        future = self._parallel_pool.submit(func, ctx)
        return future.result()

    def __getattr__(self, name):
        return getattr(self._core, name)

__all__ = ["TheusEngine", "TransactionError", "SecurityViolationError"]

# Re-defined locally to fix import circularity
class FilteredDomainProxy:
    """
    [v3.0.4] Proxy that filters access to domain keys based on contract inputs.
    Raises ContractViolationError if accessing a key not declared in inputs.
    """
    def __init__(self, domain_data, allowed_keys, zone_name="domain"):
        self._data = domain_data
        self._allowed = allowed_keys  # Set of allowed key names (e.g., {'counter'})
        self._zone = zone_name
    
    def __getitem__(self, key):
        if key not in self._allowed:
            raise ContractViolationError(
                f"Access denied: '{self._zone}.{key}' not declared in contract inputs. "
                f"Allowed: {list(self._allowed)}"
            )
        if hasattr(self._data, '__getitem__'):
            return self._data[key]
        return getattr(self._data, key)
    
    def __getattr__(self, name):
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        return self[name]
    
    def get(self, key, default=None):
        if key not in self._allowed:
            raise ContractViolationError(
                f"Access denied: '{self._zone}.{key}' not declared in contract inputs."
            )
        if hasattr(self._data, 'get'):
            return self._data.get(key, default)
        return getattr(self._data, key, default)


class RestrictedStateProxy:
    """
    [v3.0.4] Read-only state proxy that enforces contract input restrictions.
    """
    def __init__(self, state, allowed_paths=None):
        self._state = state
        self._allowed_paths = allowed_paths or []
        # Parse allowed paths into zone-specific key sets
        self._domain_keys = set()
        self._global_keys = set()
        self._heavy_keys = set()
        for path in self._allowed_paths:
            parts = path.split('.')
            if len(parts) >= 2:
                zone, key = parts[0], parts[1]
                if zone == 'domain':
                    self._domain_keys.add(key)
                elif zone in ('global', 'global_'):
                    self._global_keys.add(key)
                elif zone == 'heavy':
                    self._heavy_keys.add(key)
            elif len(parts) == 1:
                # Root-level access (e.g., 'domain') - allow all keys in that zone
                zone = parts[0]
                if zone == 'domain':
                    self._domain_keys = None  # None = wildcard
                elif zone in ('global', 'global_'):
                    self._global_keys = None
                elif zone == 'heavy':
                    self._heavy_keys = None
    
    @property
    def data(self):
        return self._state.data
        
    @property
    def heavy(self):
        if self._heavy_keys is None:  # Wildcard
            return self._state.heavy
        return FilteredDomainProxy(self._state.heavy, self._heavy_keys, "heavy")
        
    @property
    def version(self):
        return self._state.version
    
    @property
    def domain(self):
        if self._domain_keys is None:  # Wildcard
            return self._state.domain
        return FilteredDomainProxy(self._state.domain, self._domain_keys, "domain")
        
    @property
    def global_(self):  # global is reserved
        if self._global_keys is None:  # Wildcard
            return self._state.global_
        return FilteredDomainProxy(self._state.global_, self._global_keys, "global")
