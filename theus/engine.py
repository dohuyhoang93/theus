from contextlib import contextmanager

try:
    from theus_core import TheusEngine as TheusEngineRust, State 
    from theus.structures import StateUpdate, ContextError
    from theus.contracts import SemanticType, ContractViolationError
except ImportError:
    class TheusEngineRust:
        def __init__(self): pass
        def execute_process_async(self, name, func): pass
    StateUpdate = None
    State = None
    class SemanticType:
        PURE = "pure"
    class ContractViolationError(Exception): pass

class SecurityViolationError(Exception):
    pass

class TransactionError(Exception):
    pass


class RestrictedStateProxy:
    def __init__(self, state):
        self._state = state
    
    @property
    def data(self):
        return self._state.data
        
    @property
    def heavy(self):
        return self._state.heavy
        
    @property
    def version(self):
        return self._state.version
    
    @property
    def domain(self):
        return self._state.domain
        
    @property
    def global_(self): # global is reserved
        return self._state.global_

    @property
    def domain_ctx(self):
        """Alias for domain (Backwards Compatibility for PURE processes)."""
        return self._state.domain

class TheusEngine:
    def __init__(self, context=None, strict_mode=True, audit_recipe=None):
        self._core = TheusEngineRust()
        self._registry = {} # name -> func
        self._audit = None
        self._interpreter_pool = None # Lazy init
        
        if audit_recipe:
             # Unwrap Hybrid Config (if present)
             rust_recipe = audit_recipe
             if hasattr(audit_recipe, 'rust_recipe'):
                 rust_recipe = audit_recipe.rust_recipe

             try:
                 from theus_core import AuditSystem
                 self._audit = AuditSystem(rust_recipe)
             except ImportError:
                 pass
        
        # 3. Wire up Core (Bug Fix)
        if hasattr(self._core, 'set_strict_mode'):
            self._core.set_strict_mode(strict_mode)
            
        if self._audit and hasattr(self._core, 'set_audit_system'):
            self._core.set_audit_system(self._audit)

        if context:
            data = {}
            if hasattr(context, "domain_ctx"):
                data["domain"] = context.domain_ctx
            if hasattr(context, "global_ctx"):
                data["global"] = context.global_ctx
            if hasattr(context, "input_ctx"):
                data["input"] = context.input_ctx
                
            if data:
                try:
                    self.compare_and_swap(self.state.version, data=data)
                except Exception:
                    pass

    def get_pool(self):
        if self._interpreter_pool is None:
             from theus.parallel import InterpreterPool, INTERPRETERS_SUPPORTED, ParallelContext
             if not INTERPRETERS_SUPPORTED:
                 raise RuntimeError("PEP 554 Sub-interpreters not supported on this Python runtime.")
             self._interpreter_pool = InterpreterPool(size=2)
             self._ParallelContext = ParallelContext 
        return self._interpreter_pool


    def execute_parallel(self, process_name, **input_args):
        """
        Executes a registered process in a true parallel sub-interpreter.
        """
        # 1. Resolve function
        func = self._registry.get(process_name)
        if not func:
            raise ValueError(f"Process '{process_name}' not found for parallel execution")
            
        pool = self.get_pool()
        
        # 2. Prepare isolated context/args
        current_domain = self.state.domain.to_dict() if hasattr(self.state.domain, 'to_dict') else {}
        if input_args:
            current_domain.update(input_args)
        
        # Use global picklable class from parallel module
        ctx_data = self._ParallelContext(current_domain)
        
        # 3. Submit
        future = pool.submit(func, ctx_data)
        result = future.result() 
        
        return result



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
        ctx = {
            'domain': data.get('domain', None),
            'global': data.get('global', None),
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
            
        loop.run_until_complete(self.execute(name, **kwargs))

    @property
    def state(self):
        return self._core.state

    def transaction(self):
        return self._core.transaction()
        
    def compare_and_swap(self, *args, **kwargs):
        return self._core.compare_and_swap(*args, **kwargs)

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
        Extended v3.0: Supports Audit Integration (Exceptions) and POP Output Mapping.
        """
        # Resolve function
        if isinstance(func_or_name, str):
            func = self._registry.get(func_or_name)
            if not func:
                raise ValueError(f"Process '{func_or_name}' not found in registry")
        else:
            func = func_or_name

        contract = getattr(func, "_pop_contract", None)

        # Runtime Semantic Firewall (View Restriction)
        target_func = func  
        if contract and contract.semantic == SemanticType.PURE:
             # Pure Wrapper Logic
             import inspect
             if inspect.iscoroutinefunction(func):
                  async def safe_wrapper(ctx, *a, **k):
                      restricted = self._create_restricted_view(ctx)
                      return await func(restricted, *a, **k)
                  safe_wrapper.__name__ = func.__name__
                  target_func = safe_wrapper
             else:
                  def safe_wrapper(ctx, *a, **k):
                      restricted = self._create_restricted_view(ctx)
                      return func(restricted, *a, **k)
                  safe_wrapper.__name__ = func.__name__
                  target_func = safe_wrapper

        # Capture version for CAS
        start_version = None
        if hasattr(self._core, "state"):
             try:
                 start_version = self.state.version
             except:
                 pass

        # Execute with Audit Hook
        try:
            result = await self._core.execute_process_async(func.__name__, target_func)
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
                         if hasattr(curr_wrapper, "to_dict"):
                              updates_by_root[key] = curr_wrapper.to_dict()
                         elif isinstance(curr_wrapper, dict):
                              updates_by_root[key] = curr_wrapper.copy()
                         else:
                              updates_by_root[key] = {}
                     
                     if len(rest) > 0:
                         updates_by_root[key][rest[0]] = val
            
            if start_version is not None:
                 final_heavy = new_heavy if new_heavy else None
                 self._core.compare_and_swap(start_version, updates_by_root, final_heavy, None)
            
            return result
        
        return result
    
    def _create_restricted_view(self, ctx):
        # Create a restricted view (No Signal) via Rust method + Proxy wrapper
        # The Rust method clears the signal dict (Defense in check)
        # The Proxy ensures AttributeError on access attempt (Interface/API Contract)
        return RestrictedStateProxy(ctx.restrict_view())
        
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
                  raise SecurityViolationError(f"Write permission denied for path '{check_key}'")

    @contextmanager
    def edit(self):
        """Safe Zone for external mutation (v2 compat stub)."""
        yield self

    def __getattr__(self, name):
        return getattr(self._core, name)

__all__ = ["TheusEngine", "TransactionError", "SecurityViolationError"]
