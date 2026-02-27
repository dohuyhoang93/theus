import os
import sys
import threading
import dataclasses
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union, Callable

# Load Core Rust Module
try:
    import theus_core
    # [v3.3 Compatibility] Export SupervisorProxy for legacy tests
    try:
        from theus_core import SupervisorProxy
    except ImportError:
        class SupervisorProxy(dict): pass

    from theus.structures import StateUpdate, FunctionResult

    _HAS_RUST_CORE = True
except ImportError as e:
    _HAS_RUST_CORE = False
    print(f"WARNING: 'theus_core' not found. Reason: {e}")
    print("Running in Pure Python Fallback (Slower).")

from theus.context import BaseSystemContext, TransactionError, NamespaceRegistry, NamespacePolicy
from theus.contracts import SemanticType, ContractViolationError
from theus.guards import ContextGuard

# [v3.3 Compatibility] Export ContextGuard as SupervisorProxy for legacy/manual transactions
SupervisorProxy = ContextGuard

SecurityViolationError = ContractViolationError


class TheusEngine:
    """
    Theus v3.0 Main Engine.
    Orchestrates Context, Processes, and Rust Core Transaction Manager.

    Args:
        context: Initial context data (optional)
        namespaces: List of Namespace configurations (optional, [RFC-002])
        strict_guards: Enable strict contract enforcement (default: True)
        strict_cas: Enable Strict CAS mode (default: False)
        audit_recipe: Audit configuration (optional)
    """

    def __init__(
        self, context=None, namespaces=None, strict_guards=True, strict_cas=False, audit_recipe=None
    ):
        self._namespaces = NamespaceRegistry()
        self._strict_guards = strict_guards # Renamed from strict_mode
        self._strict_cas = strict_cas  # v3.0.4: CAS mode control
        self._audit = None
        self._schema = None  # v3.1.2: Schema Validation

        # 1. Standardize Context
        if context is None:
            self._context = BaseSystemContext()
        elif isinstance(context, dict):
            # [Fix] Wrap raw dict in BaseSystemContext to support RFC-001/002 linkage
            self._context = BaseSystemContext(
                domain=context.get("domain"),
                global_ctx=context.get("global_ctx") or context.get("global") or context.get("global_")
            )
        else:
            self._context = context

        # 2. [RFC-002] Register Namespaces and Collect Data
        # We don't store data in the Registry singleton anymore to avoid test pollution.
        init_data = {}
        if namespaces:
            for ns in namespaces:
                if isinstance(ns, dict):
                    name = ns["name"]
                    policy = ns.get("policy")
                    data = ns.get("data", {})
                    self._namespaces.register(name, policy)
                    init_data[name] = data
                else:
                    self._namespaces.register(ns[0], ns[1] if len(ns) > 1 else None)
                    if len(ns) > 2:
                        init_data[ns[0]] = ns[2]

        # Merge Context Data into Init Data
        def _dump_context(obj):
            """Recursively dump context into primitives for Rust Core."""
            if obj is None: return None
            if hasattr(obj, "to_dict"): return obj.to_dict()
            if hasattr(obj, "model_dump"): return obj.model_dump()
            if hasattr(obj, "dict"): return obj.dict()
            if isinstance(obj, dict):
                 return {k: _dump_context(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                 return [_dump_context(v) for v in obj]
            if hasattr(obj, "__dict__"):
                 return {k: _dump_context(v) for k, v in vars(obj).items() if not k.startswith("_")}
            return obj

        if hasattr(self, "_context"):
            dumped = _dump_context(self._context)
            if isinstance(dumped, dict):
                init_data.update(dumped)

        # [RFC-001] Parse explicit Zone Physics overrides from type annotations
        def _parse_physics_overrides(obj, path_prefix=""):
            if obj is None: return
            
            # NOTE: Pydantic v2.11+ deprecates accessing model_fields on instances.
            # Access on the CLASS instead to avoid DeprecationWarning.
            obj_class = type(obj) if not isinstance(obj, type) else obj
            fields = getattr(obj_class, "model_fields", None) or getattr(obj_class, "__fields__", None)
            annotations = {}
            if fields:
                for name, field_info in fields.items():
                    # NOTE: Pydantic v2 uses `annotation`, v1 uses `type_`.
                    # Use getattr with None fallback to handle both versions safely.
                    ann = getattr(field_info, "annotation", None) or getattr(field_info, "type_", None)
                    if ann is not None:
                        annotations[name] = ann
            elif hasattr(obj_class, "__annotations__"):
                annotations = obj_class.__annotations__
            else:
                annotations = getattr(obj_class, "__annotations__", {})

            for name, ann in annotations.items():
                if hasattr(ann, "__metadata__"):
                    from theus.context import Mutable, AppendOnly, Immutable, PYTHON_PHYSICS_OVERRIDES
                    full_path = f"{path_prefix}.{name}" if path_prefix else name
                    for meta in ann.__metadata__:
                        if meta is Mutable or isinstance(meta, Mutable):
                            # Data CAP: READ | APPEND | UPDATE | DELETE = 15
                            if _HAS_RUST_CORE: theus_core.register_physics_override(full_path, 15)
                            PYTHON_PHYSICS_OVERRIDES[full_path] = 15
                        elif meta is AppendOnly or isinstance(meta, AppendOnly):
                            # CAP_READ | CAP_APPEND = 3
                            if _HAS_RUST_CORE: theus_core.register_physics_override(full_path, 3)
                            PYTHON_PHYSICS_OVERRIDES[full_path] = 3
                        elif meta is Immutable or isinstance(meta, Immutable):
                            # CAP_READ = 1
                            if _HAS_RUST_CORE: theus_core.register_physics_override(full_path, 1)
                            PYTHON_PHYSICS_OVERRIDES[full_path] = 1
                
                # Recurse
                val = getattr(obj, name, None)
                if val is not None and not isinstance(val, (int, float, str, bool, list, dict)):
                    _parse_physics_overrides(val, f"{path_prefix}.{name}" if path_prefix else name)

        if _HAS_RUST_CORE and hasattr(theus_core, "register_physics_override"):
            theus_core.clear_physics_overrides() # Reset on engine init
            if hasattr(self, "_context"):
                # Top-level is usually BaseSystemContext
                _parse_physics_overrides(self._context, "")
                # Also explicitly parse common namespaces to ensure path prefixes like 'domain.X' match
                for ns_name in ["domain", "global_ctx", "global"]:
                    if hasattr(self._context, ns_name):
                        val = getattr(self._context, ns_name)
                        if val is not None:
                             _parse_physics_overrides(val, "domain" if ns_name == "domain" else "global")

        self._registry = {} # Legacy internal registry (processes)

        # Load Audit Config if available
        # v3.0.2: Standardized ConfigFactory Usage (Arg > File)
        audit_config = audit_recipe
        if not audit_config:
            from theus.config import ConfigFactory

            audit_config = ConfigFactory.load_audit_recipe()

        if audit_config:
            # Unwrap AuditRecipeBook if necessary
            if isinstance(audit_config, str):
                from theus.config import ConfigFactory
                try:
                    book = ConfigFactory.load_recipe(audit_config)
                    audit_config = book.rust_recipe
                except Exception:
                     # Fallback if file not found or invalid?
                     # Let's assume it works or fail hard
                     pass

            if hasattr(audit_config, "rust_recipe"):
                audit_config = audit_config.rust_recipe
            elif isinstance(audit_config, dict):
                # [v3.1.2] Automatic Dict -> AuditRecipe conversion
                from theus.config import AuditRecipe
                target = audit_config.get("audit", audit_config)
                t_max = target.get("threshold_max", 3)
                reset = target.get("reset_on_success", True)
                audit_config = AuditRecipe(threshold_max=int(t_max), reset_on_success=bool(reset))

            from theus.audit import AuditSystem
            self._audit = AuditSystem(audit_config)

        # Initialize Rust Core (Microkernel)
        if _HAS_RUST_CORE:
            # [RFC-002] init_data is now local (collected above)
            self._core = theus_core.TheusEngine()  # No args
            
            # [POP v3.1] Explicit Decoupling of Strictness Flags
            self._core.set_strict_guards(strict_guards)
            self._core.set_strict_cas(strict_cas)

            # Hydrate state via CAS (Version 0 -> Init)
            if init_data:
                try:
                    # [v3.1 FIX] Rust Core initializes State at Version 0 (Empty)
                    self._core.compare_and_swap(0, init_data)
                except Exception as e:
                    print(f"WARNING: Initial hydration failed: {e}")

            # Link Context to Engine State (Zero-Copy Link)
            if hasattr(self._context, "_state"):
                 # Use object.__setattr__ to bypass any mixin locks
                 object.__setattr__(self._context, "_state", self._core.state)

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

        # [v3.1.2] Audit & Validator Wiring
        if self._audit:
            # 1. Connect Python Audit System to Rust Core (One Brain)
            # This ensures Rust-side CAS events log to the same RingBuffer
            if hasattr(self._core, "set_audit_system"):
                 self._core.set_audit_system(self._audit)

            # 2. Initialize Active Validator (Gates)
            # We need to re-parse definitions because AuditSystem only holds the Rust Recipe (Thresholds)
            from theus.config import ConfigFactory
            from theus.validator import AuditValidator
            
            definitions = {}
            # Re-read config source
            src = audit_recipe 
            if not src:
                 # If implied via None -> load default
                 src = "audit_recipe.yaml"
            
            if isinstance(src, str):
                 try:
                     book = ConfigFactory.load_recipe(src)
                     definitions = book.definitions
                 except Exception:
                     pass # Ignore if file missing during implicit load
            elif isinstance(src, dict):
                 definitions = src.get("process_recipes", {})

            self._validator = AuditValidator(definitions, self._audit)
        else:
            self._validator = None

        self._parallel_pool = None

    @property
    def strict_guards(self):
        return self._strict_guards
    
    @strict_guards.setter
    def strict_guards(self, enabled: bool):
        self._strict_guards = enabled
        if hasattr(self._core, "set_strict_guards"):
            self._core.set_strict_guards(enabled)

    @property
    def strict_cas(self):
        return self._strict_cas

    @strict_cas.setter
    def strict_cas(self, enabled: bool):
        self._strict_cas = enabled
        if hasattr(self._core, "set_strict_cas"):
            self._core.set_strict_cas(enabled)

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
                    spec = importlib.util.spec_from_file_location(
                        module_name, file_path
                    )
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

    async def execute_workflow(self, yaml_path, **kwargs):
        """
        Execute Workflow YAML using Rust Flux DSL Engine.
        Runs in a separate thread to prevent blocking the asyncio event loop (INC-008).
        """
        from theus_core import WorkflowEngine
        import os
        import asyncio

        # Read YAML properly
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_content = f.read()

        # [DX] Allow overrides via kwargs, fallback to Env Var
        max_ops = kwargs.get("max_ops", int(os.environ.get("THEUS_MAX_LOOPS", 10000)))
        
        # [DX] Allow explicit debug=True in kwargs
        env_debug = os.environ.get("THEUS_FLUX_DEBUG", "0").lower() in ("1", "true", "yes")
        debug = kwargs.get("debug", env_debug)

        # Create Engine instance (lightweight)
        wf_engine = WorkflowEngine(yaml_content, max_ops, debug)

        # Build context dict for condition evaluation
        data = self.state.data

        # v3.3: Inject Signal Snapshot
        signals = {}
        if hasattr(self.state, "signals"):
            signals = self.state.signals

        ctx = {
            "domain": data.get("domain", None),
            "global": data.get("global", None),
            "signal": signals,
            "cmd": signals,
        }

        # Offload the blocking Rust execution to a thread
        # The callback _run_process_sync will be called from that thread.
        executed = await asyncio.to_thread(
            wf_engine.execute, ctx, self._run_process_sync
        )

        return executed

    def _run_process_sync(self, name: str, **kwargs):
        """Run a process synchronously (blocking). Called by Rust Flux Engine."""
        import asyncio
        import warnings

        # [DX Check] Warn if called from Event Loop
        try:
            asyncio.get_running_loop()
            warnings.warn(
                f"Blocking execution of '{name}' detected inside Async Event Loop! "
                "This will cause a DEADLOCK. Use 'await asyncio.to_thread(engine.execute_workflow, ...)'",
                RuntimeWarning,
            )
        except RuntimeError:
            pass

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Blocking call from Rust, but loop is running (likely we are in a thread)
            # Schedule coroutine and wait for result safely
            future = asyncio.run_coroutine_threadsafe(
                self.execute(name, **kwargs), loop
            )
            return future.result()
        else:
            loop.run_until_complete(self.execute(name, **kwargs))

    @property
    def state(self):
        """v3.3 Returns the Rust Core State object (Hybrid View)."""
        core_state = self._core.state
        instance = self
        
        # [v3.3 FIX] Cache StateView to preserve identity (fixes test_transaction_rollback.py)
        curr_ver = core_state.version
        if getattr(self, "_cached_state_ver", -1) == curr_ver:
             if hasattr(self, "_cached_state_view"):
                  return self._cached_state_view

        class StateView:
            @property
            def version(self): return core_state.version
            @property
            def data(self):
                # Hybrid View prioritizing Context Objects
                class HybridData:
                    def __getitem__(self, key):
                        # 1. Try Pydantic/Object from Context
                        val = getattr(instance._context, key, None)
                        if val is not None:
                             # Decide whether to wrap in ContextGuard for hybrid subscript support.
                             # Only wrap objects that lack native __getitem__ AND are not Pydantic models.
                             # Return Pydantic models and primitives directly to preserve isinstance() checks.
                             is_primitive = isinstance(val, (int, float, str, bool, list, dict, type(None), ContextGuard))
                             try:
                                 from pydantic import BaseModel as PydanticBase
                                 is_pydantic = isinstance(val, PydanticBase)
                             except ImportError:
                                 is_pydantic = False
                             has_subscript = hasattr(type(val), "__getitem__") and not is_pydantic
                             if not is_primitive and not is_pydantic and not has_subscript:
                                  proxy = getattr(val, "_theus_proxy", None)
                                  # NOTE: _inner must be non-None to skip Rust guard construction.
                                  return ContextGuard(
                                      val, 
                                      allowed_inputs={"*"}, 
                                      allowed_outputs={"*"},
                                      _inner=proxy or val,
                                      process_name="StateView"
                                  )
                             return val
                        # 2. Try Rust Core Proxy
                        return core_state.data[key]
                    def __getattr__(self, name): return getattr(core_state.data, name)
                    def __repr__(self): return repr(core_state.data)
                    def keys(self): return core_state.data.keys()
                    def items(self): return core_state.data.items()
                    def __iter__(self): return iter(core_state.data)
                    def __len__(self): return len(core_state.data)
                return HybridData()
            
            def __getattr__(self, name): return getattr(core_state, name)
            def __repr__(self): return f"<StateView v{self.version}>"
            
        view = StateView()
        object.__setattr__(self, "_cached_state_ver", curr_ver)
        object.__setattr__(self, "_cached_state_view", view)
        return view

    @property
    def heavy(self):
        """v3.1 Managed Memory Allocator"""
        return self._allocator

    def transaction(self, write_timeout_ms=5000):
        """v3.3 Returns a Transaction Context Manager (with Auto-Sync)."""
        instance = self
        
        @contextmanager
        def sync_transaction(core, timeout):
            with theus_core.Transaction(core, write_timeout_ms=timeout) as tx:
                yield tx
            
            # Post-Commit Sync (Success only)
            instance._sync_registry_from_core()
            
        return sync_transaction(self._core, write_timeout_ms)

    def compare_and_swap(self, expected_version, data=None, heavy=None, signal=None, requester=None):
        """
        Compare-And-Swap with configurable conflict detection.

        Behavior depends on `strict_cas` setting:
        - strict_cas=False (default): Rust Smart CAS with Key-Level detection.
          Allows merge when specific keys haven't changed since expected_version.
        - strict_cas=True: Strict mode - rejects ALL version mismatches.

        Args:
            requester (str, optional): Name of process/worker. Required for Priority Ticket (VIP) access.

        Returns:
            None on success, State object on failure (strict mode),
            or raises ContextError on conflict (smart mode).
        """
        # [REMOVED] Python-side Pre-flight check.
        # We delegate strictness entirely to Rust Core (v3.0).
        # if self._strict_cas: ...

        # Delegate to Rust Core (Smart CAS with Key-Level detection)
        res = self._core.compare_and_swap(
            expected_version, data=data, heavy=heavy, signal=signal, requester=requester
        )
        
        return res

    def _sync_registry_from_core(self):
        """Syncs the current Rust Core state back to the NamespaceRegistry and Context object."""
        if not hasattr(self, "_core"): return
        try:
            data = self._core.state.data
            # 1. Sync Namespaces (Legacy Registry)
            for name, ns_info in self._namespaces._namespaces.items():
                if name == "default":
                    ns_info["data"] = {k: v for k, v in data.items() if k not in self._namespaces._namespaces}
                elif name in data:
                    ns_info["data"] = data[name]
            
            # 2. Sync Context Fields (Pydantic/Object)
            if hasattr(self, "_context"):
                for field_name in ["domain", "global_ctx", "global"]:
                    core_key = "global" if field_name == "global_ctx" else field_name
                    if core_key in data and hasattr(self._context, field_name):
                        curr_val = getattr(self._context, field_name)
                        if curr_val is not None:
                            # Try to update in-place or re-validate to maintain Type
                            model_cls = type(curr_val)
                            try:
                                native_proxy = data[core_key]
                                if hasattr(model_cls, "model_validate"):
                                    new_obj = model_cls.model_validate(native_proxy)
                                elif hasattr(model_cls, "parse_obj"):
                                    new_obj = model_cls.parse_obj(native_proxy)
                                else:
                                    # [v3.1.2] Fallback for standard dataclasses (preserves Type and Identity)
                                    if dataclasses.is_dataclass(curr_val):
                                         for f in dataclasses.fields(curr_val):
                                              if f.name in native_proxy:
                                                   try: setattr(curr_val, f.name, native_proxy[f.name])
                                                   except: pass
                                         new_obj = curr_val
                                    else:
                                        new_obj = native_proxy
                                
                                # Attach native proxy for ContextGuard chain (Hybrid Bridge)
                                if new_obj is not None:
                                     try: object.__setattr__(new_obj, "_theus_proxy", native_proxy)
                                     except: pass
                                object.__setattr__(self._context, field_name, new_obj)
                            except Exception:
                                # Safe fallback
                                object.__setattr__(self._context, field_name, data[core_key])
        except Exception:
            pass # Never block execution success for sync failures

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
                        raise ContractViolationError(
                            f"Pure process cannot take inputs from Zone: Signal/Meta (Found: {inp})"
                        )

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

        # [v3.3] Extract Retry Config
        # Fixes TypeError: func() got unexpected keyword argument 'retries'
        max_retries = kwargs.pop("retries", 0)
        current_retries = 0

        # [v3.3 FIX] Hoist Transaction to preserve Outbox across CAS retries
        # Previously tx was created inside _attempt_execute, causing message loss on retry.
        while True:
            with theus_core.Transaction(self._core) as tx:
                try:
                    result = await self._attempt_execute(func, tx, *args, **kwargs)

                    # If success, clear conflict counter
                    if hasattr(self._core, "report_success"):
                        self._core.report_success(func.__name__)

                    # [v3.3] Manual Flush for Flux Engine (Fix for Outbox msg loss)
                    if hasattr(self._core, "flush_outbox"):
                        self._core.flush_outbox()

                    # Transaction commits when block exits
                    pass
                except Exception as e:
                    # Check for CAS Conflict (ContextError)
                    err_msg = str(e)
                    is_cas_error = "CAS Version Mismatch" in err_msg
                    is_busy_error = "System Busy" in err_msg
                    
                    # [RE-ENABLED FOR DIAGNOSIS]
                    import sys
                    print(f"[DEBUG] Execute Exception: {err_msg!r} | CAS={is_cas_error} | Busy={is_busy_error}", file=sys.stderr)
                    sys.stderr.flush()

                    if is_busy_error:
                        is_cas_error = True 

                    should_retry = False
                    backoff_ms = 50

                    if is_cas_error:
                        # 1. Try Rust Core Logic first
                        if hasattr(self._core, "report_conflict"):
                            decision = self._core.report_conflict(func.__name__)
                            if decision.should_retry:
                                should_retry = True
                                backoff_ms = decision.wait_ms
                        
                        # 2. Fallback to Python Manual Retry with CAPPED Backoff + Full Jitter
                        if not should_retry and current_retries < max_retries:
                            should_retry = True
                            current_retries += 1
                            
                            MAX_BACKOFF_MS = 1000
                            raw_backoff = 50 * (2 ** (current_retries - 1))
                            
                            import random
                            actual_backoff = random.uniform(0, min(MAX_BACKOFF_MS, raw_backoff))
                            
                            backoff_ms = actual_backoff
                            print(f"[*] CAS/Busy Conflict for {func.__name__}. Retry {current_retries}/{max_retries} in {backoff_ms:.2f}ms...")

                    if should_retry:
                        await asyncio.sleep(backoff_ms / 1000.0)
                        continue

                    raise e
            
            # Successful COMMIT. Sync back to registry for legacy tests.
            self._sync_registry_from_core()
            return result

    async def _attempt_execute(self, func, tx, *args, **kwargs):
        # [v3.1.2] Input Gate: Active Validation
        if self._validator:
             self._validator.validate_inputs(func.__name__, kwargs)

        contract = getattr(func, "_pop_contract", None)

        # v3.0.2: Auto-Dispatch Parallel Processes
        # Transaction Management (v3.1 Explicit Lifecycle)
        # Transaction is now passed from execute() to preserve Outbox across retries.
        start_version = self.state.version
        
        result = None
        ran_locally = True

        # v3.0.2: Auto-Dispatch Parallel Processes
        if contract and contract.parallel:
            import asyncio
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: self.execute_parallel(func.__name__, **kwargs)
            )
            ran_locally = False
            
        if ran_locally:
            target_func = func
            if contract and contract.semantic == SemanticType.PURE:
                # Pure Wrapper Logic + Arg Capture
                # [v3.0.4] Pass contract.inputs to create filtered restricted view
                allowed_inputs = contract.inputs if contract else []
                import inspect

                if inspect.iscoroutinefunction(func):

                    async def safe_wrapper(ctx, *_, **__):
                        restricted = self._create_restricted_view(
                            ctx, allowed_paths=allowed_inputs
                        )
                        return await func(restricted, *args, **kwargs)

                    safe_wrapper.__name__ = func.__name__
                    target_func = safe_wrapper
                else:

                    def safe_wrapper(ctx, *_, **__):
                        restricted = self._create_restricted_view(
                            ctx, allowed_paths=allowed_inputs
                        )
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
                        # [v3.3 FIX] Extract outbox BEFORE creating ContextGuard
                        # ProcessContext.outbox is a #[pyo3(get)] read-only attribute
                        raw_outbox = ctx.outbox
                        
                        native_guard = ContextGuard(
                            ctx, 
                            set(contract.inputs if contract else []), 
                            set(contract.outputs if contract else []), 
                            "", 
                            tx, 
                            self._strict_guards, 
                            func.__name__
                        )
                        return await func(native_guard, *args, **kwargs)

                    arg_binder.__name__ = func.__name__
                    target_func = arg_binder
                else:

                    def arg_binder(ctx, *_, **__):
                        native_guard = ContextGuard(
                            ctx, 
                            set(contract.inputs if contract else []), 
                            set(contract.outputs if contract else []), 
                            "", 
                            tx, 
                            self._strict_guards, 
                            func.__name__
                        )
                        return func(native_guard, *args, **kwargs)

                    arg_binder.__name__ = func.__name__
                    target_func = arg_binder

            # Run via Rust Core (Handles Audit, Timing, etc)
            try:
                result = await self._core.execute_process_async(
                    func.__name__, target_func, tx
                )
            except Exception as e:
                # Local execution failure
                # If we have audit, log fail? 
                # Currently standard flow catches exception at line 563
                raise e

        # Common Path: Commit Logic (Local or Parallel Result)
        try:

            # v3.1 Explicit Commit (Supervisor Mode)
            # Verify state version to ensure Optimistic Concurrency Control
            # current_ver = self.state.version (Already captured as start_version)

            # [v3.1 Zero Trust Memory: Delta Replay Commit]
            # Instead of shadow copy, replay delta_log onto fresh dict for CAS
            pending_data = tx.build_pending_from_deltas()

            # [v3.1.1] Limit pending_data noise
            # If pending_data has 'domain' as None? No.

            # [v3.1.2] Schema Validation (Python Side)
            # Enforce Pydantic constraints before CAS
            if self._schema and self._strict_guards:
                self._validate_schema(pending_data)

            # [v3.1.2] Output Gate: Active Validation (Schema/RuleSpec)
            if self._validator:
                self._validator.validate_outputs(func.__name__, pending_data)

            # [v3.1.2] Output Gate: Active Validation (Schema/RuleSpec)
            if self._validator:
                self._validator.validate_outputs(func.__name__, pending_data)

            # [v3.1.1] Audit Gatekeeper: Validate Contract BEFORE Commit
            # This ensures strict spec compliance (Zero Trust).
            if contract and self._strict_guards:
                self._validate_contract_compliance(
                    func.__name__, contract, pending_data, tx
                )

            # Logic for Output Mapping
            # 1. StateUpdate (Explicit)
            if StateUpdate and isinstance(result, StateUpdate):
                if contract:
                    self._check_output_permission(result, contract)

                if result.key is not None:
                    parts = result.key.split(".")
                    root = parts[0]
                    if root not in pending_data:
                        curr_wrapper = getattr(self.state, root, None)
                        if hasattr(curr_wrapper, "to_dict"):
                            pending_data[root] = curr_wrapper.to_dict()
                        elif isinstance(curr_wrapper, dict):
                            pending_data[root] = curr_wrapper.copy()
                        else:
                            pending_data[root] = curr_wrapper

                    if len(parts) == 1:
                        if result.val is not None:
                            pending_data[root] = result.val
                    else:
                        target = pending_data[root]
                        if target is None:
                            target = {}
                            pending_data[root] = target

                        for part in parts[1:-1]:
                            if isinstance(target, dict):
                                target = target.setdefault(part, {})
                            else:
                                target = getattr(target, part)
                        last = parts[-1]
                        if isinstance(target, dict):
                            if result.val is not None:
                                target[last] = result.val
                        else:
                            # For objects, we might set None if explicit?
                            # But usually safe to avoid overwriting with None if not intended
                            if result.val is not None:
                                setattr(target, last, result.val)

                # [v3.1.5 FIX] Handle Bulk Data Update
                if result.data:
                    for path, val in result.data.items():
                        parts = path.split(".")
                        root = parts[0]
                        if root not in pending_data:
                            # [v3.1.5] Smart CAS Optimization: 
                            # Do NOT clone full state. Use empty dict to trigger Rust Deep Merge.
                            # This avoids false conflicts on untouched keys.
                            pending_data[root] = {}

                        if len(parts) == 1:
                            pending_data[root] = val
                        else:
                            target = pending_data[root]
                            if target is None:
                                target = {}
                                pending_data[root] = target

                            for part in parts[1:-1]:
                                if isinstance(target, dict):
                                    target = target.setdefault(part, {})
                                else:
                                    target = getattr(target, part)
                            
                            last = parts[-1]
                            if isinstance(target, dict):
                                target[last] = val
                            else:
                                setattr(target, last, val)

            # 2. POP Output Mapping (Implicit)
            elif contract and contract.outputs:
                outputs = contract.outputs

                # Decide how to unpack result
                vals = []
                if isinstance(result, dict):
                    # [v3.1 Fix] ambiguity: Is dict a Map or a Value?
                    # Check if result keys match output names (or leaves)
                    is_map = False
                    for out_key in outputs:
                        if out_key in result:
                            is_map = True
                            break
                        leaf = out_key.split(".")[-1]
                        if leaf in result:
                            is_map = True
                            break

                    if is_map:
                        # [v3.1.4] Enhanced Unpacking Strategy
                        for out_key in outputs:
                            leaf = out_key.split(".")[-1]
                            if out_key in result:
                                vals.append(result[out_key])
                            elif leaf in result:
                                vals.append(result[leaf])
                            else:
                                vals.append(None)
                    elif len(outputs) == 1:
                        vals = (result,)
                    else:
                        # Heuristic: Tuple unpacking from lists?
                        # Or strict: if keys missing and len > 1, assume map failed -> None
                        vals = [None] * len(outputs)
                else:
                    # [RFC-001 FIX] Allow None return for multi-output processes.
                    # This allows proxy-based mutations to be the sole source of truth.
                    if result is None:
                        vals = [None] * len(outputs)
                    else:
                        # [FIX v3.3] Prevent single return value from being treated as list
                        # of paths if len(outputs) > 1.
                        if len(outputs) > 1:
                            if isinstance(result, (list, tuple)):
                                vals = result
                            elif isinstance(result, dict):
                                # Map mode already handled above? No, only if it matched keys.
                                # If it's a raw dict return for a multi-output process, it's ambiguous.
                                vals = [result] + [None] * (len(outputs) - 1)
                            else:
                                raise TypeError(f"Process {func.__name__} has multiple outputs {outputs} but returned a single {type(result)}.")
                        else:
                            vals = (result,)

                for path, val in zip(outputs, vals):
                    # [FIX v3.1.3] Skip if val is None (Do not overwrite Proxy mutations)
                    if val is None:
                        continue

                    parts = path.split(".")
                    root = parts[0]
                    rest = parts[1:]

                    from .context import NamespaceRegistry
                    registry = NamespaceRegistry()

                    if root in ["heavy"]:
                        if len(rest) > 0:
                            tx.pending_heavy[rest[0]] = val
                    elif root in ["domain", "global", "global_"] or root in registry._namespaces:
                        key = "global" if root == "global_" else root

                        # Ensure root is in pending_data (Merge Base)
                        if key not in pending_data:
                            curr_wrapper = getattr(self.state, key, None)
                            
                            # If not on object, try to fetch from Registry data directly
                            if curr_wrapper is None and key in registry._namespaces:
                                curr_wrapper = registry._namespaces[key]["data"]

                            if curr_wrapper is None:
                                pending_data[key] = {}  # Auto-init
                            elif hasattr(curr_wrapper, "to_dict"):
                                pending_data[key] = curr_wrapper.to_dict()
                            elif isinstance(curr_wrapper, dict):
                                pending_data[key] = curr_wrapper.copy()
                            else:
                                # Preserve Object Identity
                                pending_data[key] = curr_wrapper

                        if len(rest) > 0:
                            # Recursive Access
                            target = pending_data[key]
                            SUCCESS = True
                            if target is None:
                                target = {}
                                pending_data[key] = target

                            for part in rest[:-1]:
                                if isinstance(target, dict):
                                    if part not in target:
                                        target[part] = {}
                                    target = target[part]
                                else:
                                    if hasattr(target, part):
                                        target = getattr(target, part)
                                    else:
                                        print(
                                            f"WARNING: Output path traversal failed at '{part}'"
                                        )
                                        SUCCESS = False
                                        break

                            if SUCCESS:
                                last_field = rest[-1]
                                if isinstance(target, dict):
                                    target[last_field] = val
                                else:
                                    setattr(target, last_field, val)

            # [v3.3 FIX] RELY ON Transaction.__exit__ for Atomic Commit
            # Do NOT call self._core.compare_and_swap here, as it causes double-bumps
            # instead, ensure all collected updates are in the Transaction object.
            tx.update(data=pending_data)

            if self._audit:
                self._audit.log_success(func.__name__)

            return result

        except Exception as e:
            if self._audit:
                try:
                    self._audit.log_fail(key=func.__name__)
                except Exception as audit_exc:
                    raise audit_exc from e
            raise e

    def set_schema(self, schema):
        """
        [v3.1.2] Register a Pydantic Schema for Strict Validation.
        """
        self._schema = schema
        if hasattr(self._core, "set_schema"):
            try:
                self._core.set_schema(schema)
            except Exception as e:
                print(f"WARNING: Rust Core set_schema failed: {e}")

    def _validate_schema(self, data):
        """
        Validates the pending data against the registered Pydantic schema.
        Raises SchemaViolationError (via ImportError fallback or explicit) on failure.
        """
        if not self._schema:
            return
        

        # [v3.1.5] Strict Validation: Force re-validation of instances
        # Pydantic (v1/v2) often trusts existing model instances.
        # We must convert to dict to force validation of modified fields.
        def _recursive_dump(obj):
            if isinstance(obj, dict):
                return {k: _recursive_dump(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_recursive_dump(v) for v in obj]
            elif hasattr(obj, "model_dump"):  # Pydantic v2
                return obj.model_dump()
            elif hasattr(obj, "dict"):  # Pydantic v1
                return obj.dict()
            else:
                return obj

        try:
            clean_data = _recursive_dump(data)

            # Pydantic v2
            if hasattr(self._schema, "model_validate"):
                self._schema.model_validate(clean_data)
            # Pydantic v1
            elif hasattr(self._schema, "validate"):
                self._schema.validate(clean_data)
            # Fallback: init
            else:
                self._schema(**clean_data)

        except Exception as e:
            # print(f"DEBUG: Schema Validation Failed: {e}")
            # Wrap in Theus Core error if available
            from theus_core import SchemaViolationError

            raise SchemaViolationError(str(e)) from e

    def _validate_contract_compliance(self, func_name, contract, pending_data, tx):
        """
        [v3.1.1] Audit Gatekeeper: Check pending changes against contract.
        Raises ContractViolationError if unlabeled side-effects are detected.
        Uses Granular Delta Log paths for precision.
        """
        import fnmatch

        # Get raw paths that were modified (e.g. "domain.user.score")
        try:
            modified_paths = tx.get_delta_log()
        except:
            # Fallback if method missing (should not happen with v3.1.1 Core)
            modified_paths = []

        # 1. PURE processes must not have side effects
        if contract.semantic == SemanticType.PURE:
            if modified_paths:
                raise ContractViolationError(
                    f"Process '{func_name}' is PURE but produced side-effects: {modified_paths}"
                )
            return

        # 2. Check Outputs compliance (Granular)
        allowed_patterns = contract.outputs or []

        for path in modified_paths:
            # [Fix v3.1.2] Ignore local/ephemeral scope changes
            if (
                path == "local"
                or path.startswith("local.")
                or path.startswith("local[")
            ):
                continue

            is_allowed = False
            # [Fix v3.1.2] Normalize path for matching (domain[meta] -> domain.meta)
            norm_path = path.replace("[", ".").replace("]", "")
            
            for pattern in allowed_patterns:
                norm_pattern = pattern.replace("[", ".").replace("]", "")
                
                # Sub-path match: pattern="domain.data", path="domain.data.x" OR "domain.data[x]"
                p_len = len(norm_pattern)
                if norm_path.startswith(norm_pattern):
                    if len(norm_path) == p_len:
                        is_allowed = True
                        break
                    # Check next char is separator
                    next_char = norm_path[p_len]
                    if next_char == ".":
                        is_allowed = True
                        break
                # Wildcard match: pattern="domain.*"
                if fnmatch.fnmatch(norm_path, norm_pattern):
                    is_allowed = True
                    break

                # [Coarse Update Leniency]
                # If path="domain" and pattern="domain.balance", allows it (with check)
                # This handles cases where Proxy reports coarse modification of parent object
                if pattern.startswith(path + ".") or pattern.startswith(path + "["):
                    is_allowed = True
                    break

            if not is_allowed:
                raise ContractViolationError(
                    f"Process '{func_name}' modified '{path}' which is NOT declared in outputs."
                    f"\nAllowed: {allowed_patterns}"
                    f"\nViolation: Access Denied to '{path}'"
                )

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
        if hasattr(self, "_core"):
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
                if hasattr(self._context, "to_dict"):
                    updates = self._context.to_dict()
                elif hasattr(self._context, "domain"):
                    # Manual extraction for BaseSystemContext
                    if hasattr(self._context.domain, "to_dict"):
                        updates["domain"] = self._context.domain.to_dict()
                    else:
                        updates["domain"] = self._context.domain.__dict__

                # Force Push
                self._core.compare_and_swap(current_ver, updates)

            except Exception as e:
                print(f"WARNING: engine.edit() failed to sync to Rust Core: {e}")

    def execute_parallel(self, process_name, **kwargs):
        """
        Execute a process in parallel pool (Sub-Interpreter or Process).
        Logic:
        1. THEUS_FORCE_INTERPRETERS=1: Force Sub-interpreters if supported.
        2. THEUS_USE_PROCESSES=1: Force ProcessPool.
        3. Windows Default: ProcessPool (for stability).
        4. Others Default: Sub-interpreters if supported.

        Args:
            process_name: Name of process to run.
            **kwargs: Arguments to pass to the process (merged into ctx.domain).

        Returns:
            Result from the process execution.
        """
        import os
        from theus.parallel import ParallelContext, INTERPRETERS_SUPPORTED
        
        # Lazy Initialization
        if self._parallel_pool is None:
            pool_size = int(os.environ.get("THEUS_POOL_SIZE", 4))
            from theus.parallel import InterpreterPool, ProcessPool
            
            # Selection Flags
            use_processes = os.environ.get("THEUS_USE_PROCESSES") == "1"
            force_interpreters = os.environ.get("THEUS_FORCE_INTERPRETERS") == "1"
            
            # Decision Tree
            if use_processes:
                self._parallel_pool = ProcessPool(size=pool_size)
            elif force_interpreters and INTERPRETERS_SUPPORTED:
                # Force means we trust the user, even if probe fails (expert mode)
                self._parallel_pool = InterpreterPool(size=pool_size)
            elif sys.platform == "win32":
                # Windows is safer with Processes by default
                self._parallel_pool = ProcessPool(size=pool_size)
            elif InterpreterPool.is_compatible():
                # On Linux/Unix, use Sub-interpreters ONLY if compatible
                self._parallel_pool = InterpreterPool(size=pool_size)
            else:
                # Fallback to Processes (e.g. Linux with NumPy < 2.1 or incompatible PyO3 core)
                self._parallel_pool = ProcessPool(size=pool_size)

        func = self._registry.get(process_name)
        if not func:
             raise ValueError(f"Process '{process_name}' not found")

        ctx = ParallelContext.from_state(self.state, **kwargs)

        # Submit and wait for result
        future = self._parallel_pool.submit(func, ctx)
        return future.result()

    def shutdown(self):
        """Cleanly shuts down internal resources (Pools, Heavies)."""
        if hasattr(self, "_parallel_pool") and self._parallel_pool:
            self._parallel_pool.shutdown()
            self._parallel_pool = None
            
        if hasattr(self, "_allocator") and self._allocator:
            self._allocator.cleanup()
            self._allocator = None

    def log(self, *args, **kwargs):
        """DX: Standard logging stub to satisfy Linter."""
        print(*args, file=sys.stderr, **kwargs)

    def attach_worker(self, worker):
        """
        [v3.3] Register a Relay Worker for Outbox Processing.
        The worker function receives OutboxMsg objects.
        """
        self._worker_ref = worker
        if hasattr(self._core, "attach_worker"):
            self._core.attach_worker(worker)

    def process_outbox(self):
        """
        [v3.3] Trigger manual processing of the Outbox queue.
        Dispatches all pending messages to the attached worker.
        """
        if hasattr(self._core, "process_outbox"):
            self._core.process_outbox()

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

    def get(self, key, default=None):
        if key not in self._allowed:
            raise ContractViolationError(
                f"Access denied: '{self._zone}.{key}' not declared in contract inputs."
            )
        
        val = default
        if hasattr(self._data, "get"):
            val = self._data.get(key, default)
        else:
            val = getattr(self._data, key, default)
        return self._wrap_deep_guard(val)

    def __getitem__(self, key):
        if key not in self._allowed:
            raise ContractViolationError(
                f"Access denied: '{self._zone}.{key}' not declared in contract inputs. "
                f"Allowed: {list(self._allowed)}"
            )
        
        val = None
        if hasattr(self._data, "__getitem__"):
            val = self._data[key]
        else:
            val = getattr(self._data, key)
        return self._wrap_deep_guard(val)

    def _wrap_deep_guard(self, val):
        """Recursively protect return values from mutation."""
        if val is None:
            return None
        if isinstance(val, (str, int, float, bool, bytes)):
            return val
        if isinstance(val, list):
            return tuple(val) # Make immutable copy
        if isinstance(val, dict):
            from types import MappingProxyType
            return MappingProxyType(val) # Zero-copy immutable view
        if hasattr(val, "copy"):
            # Try to return a copy if we don't know the type (e.g. Set)
            # Or should we be strict?
            pass
        return val

    def __getattr__(self, name):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        return self[name]

    def __setitem__(self, key, value):
        raise ContractViolationError(f"PURE Process cannot mutate state: '{self._zone}.{key}'")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            raise ContractViolationError(f"PURE Process cannot mutate state: '{self._zone}.{name}'")

    def __delitem__(self, key):
        raise ContractViolationError(f"PURE Process cannot delete state: '{self._zone}.{key}'")

    def __delattr__(self, name):
        raise ContractViolationError(f"PURE Process cannot delete state: '{self._zone}.{name}'")


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
            parts = path.split(".")
            if len(parts) >= 2:
                zone, key = parts[0], parts[1]
                if zone == "domain":
                    self._domain_keys.add(key)
                elif zone in ("global", "global_"):
                    self._global_keys.add(key)
                elif zone == "heavy":
                    self._heavy_keys.add(key)
            elif len(parts) == 1:
                # Root-level access (e.g., 'domain') - allow all keys in that zone
                zone = parts[0]
                if zone == "domain":
                    self._domain_keys = None  # None = wildcard
                elif zone in ("global", "global_"):
                    self._global_keys = None
                elif zone == "heavy":
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

