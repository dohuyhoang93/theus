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

class TheusEngine:
    def __init__(self, context=None, strict_mode=True, audit_recipe=None):
        self._core = TheusEngineRust()
        self._registry = {} # name -> func
        self._audit = None
        
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

        if context:
            data = {}
            if hasattr(context, "domain_ctx"):
                data["domain"] = context.domain_ctx
            if hasattr(context, "global_ctx"):
                data["global"] = context.global_ctx
            if hasattr(context, "input_ctx"):
                data["input"] = context.input_ctx
                
            if data:
                # Initial population
                # We use internal update because CAS might fail if version changed (unlikely here)
                # But compare_and_swap is exposed.
                try:
                    self.compare_and_swap(self.state.version, data=data)
                except Exception:
                    pass

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
        """Execute Workflow YAML using Rust Flux DSL Engine.
        
        Args:
            yaml_path: Path to YAML workflow file.
            **kwargs: Legacy kwargs (env_adapter, etc.) - ignored in v3.
        """
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
        # If PURE, create a view without Signal/Meta.
        # But we pass the function to Rust engine, which calls it with `self.state`.
        # Rust engine uses `self.state.clone_ref(py)`.
        # So we cannot easily intervene unless we modify Rust engine to accept custom context arg?
        # Rust `execute_process_async` logic: `let args = (self.state.clone_ref(py),);`
        # It hardcodes passing `self.state`.
        # To support Firewall, `execute_process_async` should support an optional `context_override`.
        # OR we wrap the function in Python before passing to Rust?
        # wrapper(ctx) -> func(restrict(ctx)).
        
        target_func = func
        
        if contract and contract.semantic == SemanticType.PURE:
            # Filter View
            # We wrap the function
            original_func = func
            
            # Since pure_wrapper might be async or sync, we need to match original.
            # But execute_process_async handles polymorphism.
            # If original is async, wrapper should be async (or return coro).
            import inspect
            if inspect.iscoroutinefunction(original_func):
                 async def safe_wrapper(ctx, *a, **k):
                     restricted = self._create_restricted_view(ctx)
                     return await original_func(restricted, *a, **k)
                 safe_wrapper.__name__ = func.__name__
                 target_func = safe_wrapper
            else:
                 def safe_wrapper(ctx, *a, **k):
                     restricted = self._create_restricted_view(ctx)
                     return original_func(restricted, *a, **k)
                 safe_wrapper.__name__ = func.__name__
                 target_func = safe_wrapper

        # Execute
        result = await self._core.execute_process_async(func.__name__, target_func)
        
        # Commit Logic (Output Scopes)
        if StateUpdate and isinstance(result, StateUpdate):
            # Check Output Permission
            if contract:
                self._check_output_permission(result, contract)
            
            # CAS Logic
            expected = result.assert_version
            if expected is not None:
                data = result.data or {}
                if result.key is not None:
                    data[result.key] = result.val
                
                heavy = result.heavy
                signal = result.signal
                d_arg = data if data else None
                h_arg = heavy if heavy else None
                s_arg = signal if signal else None
                
                self._core.compare_and_swap(expected, d_arg, h_arg, s_arg)
        
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
             # Assume keys in data are keys too? Or root keys?
             # For hierarchical checks, we need full path.
             # If update.data = {"system": {"config": "hacked"}} -> "domain.system.config" ?
             # Or "data.system.config".
             # V3 schema: root is `data`, `heavy`, `signal`.
             # `update.key` is simplified API.
             for k in update.data.keys():
                 keys_to_check.append(f"data.{k}") # Or "domain.{k}" for compat?
        
        valid_patterns = contract.outputs
        
        for key in keys_to_check:
             # Aliasing for compatibility with tests?
             # Test uses "domain.system.config".
             # If I map "data" -> "domain", then "data.x" -> "domain.x".
             # Let's verify against patterns.
             
             # Normalization
             check_key = key
             if key.startswith("data."):
                 # V3 FIX: Properly strip 'data.' prefix (len 5) to get relative path
                 # e.g. "data.domain" -> "domain"
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
