import os
import sys
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union, Callable

# Load Core Rust Module
try:
    import theus_core
    # [Fix] Handle namespace package structure (theus_core.theus_core) being installed by maturin
    if not hasattr(theus_core, "TheusEngine"):
        try:
            from theus_core import theus_core as _core_impl
            theus_core = _core_impl
        except ImportError:
            pass
            
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

    def __init__(
        self, context=None, strict_guards=True, strict_cas=False, audit_recipe=None
    ):
        self._context = context
        self._registry = {}
        self._strict_guards = strict_guards # Renamed from strict_mode
        self._strict_cas = strict_cas  # v3.0.4: CAS mode control
        self._audit = None
        self._schema = None  # v3.1.2: Schema Validation

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
            # Rust takes ownership of the Data Zone
            init_data = {}
            if context:
                if hasattr(context, "to_dict"):
                    init_data = context.to_dict()
                elif isinstance(context, dict):
                    init_data = context.copy()
                else:
                    # Fallback
                    init_data = dict(context)

            self._core = theus_core.TheusEngine()  # No args
            
            # [POP v3.1] Explicit Decoupling of Strictness Flags
            self._core.set_strict_guards(strict_guards)
            
            # strict_cas -> Concurrency (Version Mismatch)
            self._core.set_strict_cas(strict_cas)

            # Hydrate state via CAS (Version 0 -> Init)
            if init_data:
                try:
                    # [v3.1 FIX] Rust Core initializes State at Version 0 (Empty)
                    # We MUST use expected_version=0 to hydrate it successfully.
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
        return self._core.state

    @property
    def heavy(self):
        """v3.1 Managed Memory Allocator"""
        return self._allocator

    def transaction(self, write_timeout_ms=5000):
        return self._core.transaction(write_timeout_ms=write_timeout_ms)

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
        return self._core.compare_and_swap(
            expected_version, data=data, heavy=heavy, signal=signal, requester=requester
        )

        return self._core.compare_and_swap(
            expected_version, data=data, heavy=heavy, signal=signal
        )

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

                    return result

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
                        # Treat same as CAS error for retry purposes, maybe slightly shorter wait?
                        # Actually, let's use the same backoff logic to avoid Thundering Herd on lock.
                        is_cas_error = True 

                    # [v3.3] Manual Fallback Retry Logic
                    # Since Rust Core 'report_conflict' binding might be missing or limited
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
                            
                            # [Forensic Fix] Cap backoff to prevent "Exponential Explosion"
                            # Max wait = 1000ms (1s) to avoid 14-hour sleeps
                            MAX_BACKOFF_MS = 1000
                            raw_backoff = 50 * (2 ** (current_retries - 1))
                            
                            # Full Jitter: Uniform(0, min(Cap, Exp))
                            import random
                            actual_backoff = random.uniform(0, min(MAX_BACKOFF_MS, raw_backoff))
                            
                            backoff_ms = actual_backoff
                            print(f"[*] CAS/Busy Conflict for {func.__name__}. Retry {current_retries}/{max_retries} in {backoff_ms:.2f}ms...")

                    if should_retry:
                        await asyncio.sleep(backoff_ms / 1000.0)
                        continue

                    raise e

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
                        
                        native_guard = theus_core.ContextGuard(
                            ctx, 
                            contract.inputs if contract else [], 
                            contract.outputs if contract else [], 
                            None, 
                            tx, 
                            not self.strict_guards, 
                            False
                        )
                        
                        # Assign to ContextGuard's __dict__ (enabled by #[pyclass(dict)])
                        # [v3.3] Now that Rust getter is fixed, we don't need this manual assignment?
                        # object.__setattr__(native_guard, 'outbox', raw_outbox)
                        return await func(native_guard, *args, **kwargs)

                    arg_binder.__name__ = func.__name__
                    target_func = arg_binder
                else:

                    def arg_binder(ctx, *_, **__):
                        # v3.1 Guard Wrapping (Admin Mode for Non-Pure)
                        # [v3.3 FIX] Extract outbox BEFORE creating ContextGuard
                        raw_outbox = ctx.outbox
                        
                        native_guard = theus_core.ContextGuard(
                            ctx, 
                            contract.inputs if contract else [], 
                            contract.outputs if contract else [], 
                            None, 
                            tx, 
                            not self.strict_guards, 
                            False
                        )
                        # Assign to ContextGuard's __dict__ (enabled by #[pyclass(dict)])
                        # object.__setattr__(native_guard, 'outbox', raw_outbox)
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
                        if len(outputs) > 1 and not isinstance(result, (list, tuple)):
                             raise TypeError(f"Process defined multiple outputs {outputs} but returned single value: {result}. Expected tuple/list.")
                        vals = result if len(outputs) > 1 else (result,)
                        if len(outputs) == 1 and not isinstance(result, tuple):
                            vals = (result,)

                for path, val in zip(outputs, vals):
                    # [FIX v3.1.3] Skip if val is None (Do not overwrite Proxy mutations)
                    if val is None:
                        continue

                    parts = path.split(".")
                    root = parts[0]
                    rest = parts[1:]

                    if root in ["heavy"]:
                        if len(rest) > 0:
                            tx.pending_heavy[rest[0]] = val
                    elif root in ["domain", "global", "global_"]:
                        key = "global" if root == "global_" else root

                        # Ensure root is in pending_data (Merge Base)
                        if key not in pending_data:
                            curr_wrapper = getattr(self.state, key, None)
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
            
            # Selection Flags
            use_processes = os.environ.get("THEUS_USE_PROCESSES") == "1"
            force_interpreters = os.environ.get("THEUS_FORCE_INTERPRETERS") == "1"
            
            # Decision Tree
            if use_processes:
                from theus.parallel import ProcessPool
                self._parallel_pool = ProcessPool(size=pool_size)
            elif force_interpreters and INTERPRETERS_SUPPORTED:
                from theus.parallel import InterpreterPool
                self._parallel_pool = InterpreterPool(size=pool_size)
            elif sys.platform == "win32":
                # Windows is safer with Processes by default
                from theus.parallel import ProcessPool
                self._parallel_pool = ProcessPool(size=pool_size)
            elif INTERPRETERS_SUPPORTED:
                from theus.parallel import InterpreterPool
                self._parallel_pool = InterpreterPool(size=pool_size)
            else:
                # Fallback to Processes
                from theus.parallel import ProcessPool
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

