import logging
import contextvars
from typing import Any, Dict, List, Optional, Set, Union
import functools

# NOTE: Transaction is stored here instead of in ContextGuard instances to prevent
# Transaction refs from leaking into the serializable object graph. This breaks
# the Reinforcing Loop R1 (contamination cycle) identified in Systems Thinking Analysis.
_current_tx = contextvars.ContextVar('_current_tx', default=None)

try:
    import theus_core
    # Handle both maturin develop and installed structures
    if not hasattr(theus_core, "ContextGuard"):
        try:
             from theus_core import theus_core as _core_impl
             _RustContextGuard = _core_impl.ContextGuard
        except ImportError:
             # Fallback if binary is completely missing (should not happen in dev)
             _RustContextGuard = object
    else:
        _RustContextGuard = theus_core.ContextGuard
    # [RFC-001 §10] Import SupervisorProxy for __dict__ proxying wrapping check
    _RustSupervisorProxy = getattr(theus_core, "SupervisorProxy", type(None))
except ImportError:
    _RustContextGuard = object
    _RustSupervisorProxy = type(None)


class _PrivateZoneReadAccess(Exception):
    """[RFC-001 Handbook §1.1] Sentinel raised by _check_zone_physics when a non-admin
    process reads an 'internal_' (PRIVATE zone) field. The caller should return None
    instead of propagating the exception, thereby hiding the field completely."""
    pass


class ContextGuard:
    """
    Python wrapper for the Rust ContextGuard (v3.2 RFC-001).
    Provides a cleaner Python API while delegating security to the Rust Core.
    """

    def __init__(
        self,
        target_obj: Any,
        allowed_inputs: Optional[Set[str]] = None,
        allowed_outputs: Optional[Set[str]] = None,
        path_prefix: str = "",
        transaction: Any = None,
        strict_guards: bool = True,
        process_name: str = "Unknown",
        _inner: Any = None,
        parent: Any = None,
        name: Any = None,
        **kwargs
    ):
        object.__setattr__(self, "_log", logging.getLogger("theus.guards"))
        self._log.extra = {"process_name": process_name}
        
        # [v3.3 Compatibility] Allow 'path' as alias for 'path_prefix'
        if not path_prefix and "path" in kwargs:
             path_prefix = kwargs["path"]
        
        # [v3.3 Compatibility] Manual SupervisorProxy defaults to permissive access
        # Distinguish between None (Manual/Legacy) and set() (Strict Process Contract)
        if allowed_inputs is None:
             from .context import NamespaceRegistry
             allowed_inputs = set(NamespaceRegistry()._namespaces.keys())
             if not allowed_inputs: allowed_inputs = {"default", "domain", "global", "*"}
             
        if allowed_outputs is None and not kwargs.get("read_only", False):
             from .context import NamespaceRegistry
             allowed_outputs = set(NamespaceRegistry()._namespaces.keys())
             if not allowed_outputs: allowed_outputs = {"default", "domain", "global", "*"}
        elif allowed_outputs is None:
             allowed_outputs = set()
             
        # Normalize to sets for Rust Core
        allowed_inputs = set(allowed_inputs) if allowed_inputs is not None else set()
        allowed_outputs = set(allowed_outputs) if allowed_outputs is not None else set()
        
        # [v3.3 Compatibility] Handle 'read_only' flag
        if "read_only" in kwargs and kwargs["read_only"]:
             allowed_outputs = set()
        
        # We track admin status LOCALLY to avoid Illegal Read recursion in Rust
        object.__setattr__(self, "_local_is_admin", False)
        object.__setattr__(self, "_path_prefix", path_prefix)
        object.__setattr__(self, "_allowed_inputs", allowed_inputs)
        object.__setattr__(self, "_allowed_outputs", allowed_outputs)
        # NOTE: If transaction is explicitly passed, also set it in ContextVar
        # so child guards and other code can access it.
        # If None, try to recover from ContextVar (child guard creation path).
        effective_tx = transaction if transaction is not None else _current_tx.get()
        object.__setattr__(self, "_transaction", effective_tx)
        if transaction is not None:
            _current_tx.set(transaction)
        object.__setattr__(self, "_strict_guards", strict_guards)
        object.__setattr__(self, "_parent", parent)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_target", target_obj)

        if _inner is not None:
            self._inner = _inner
        else:
            # [RFC-002] Namespace Policy Pre-filtering
            # We filter the allowed lists based on Namespace Registry rules
            from .context import NamespaceRegistry
            registry = NamespaceRegistry()
            
            final_inputs = []
            for path in allowed_inputs:
                ns_name, _ = registry.resolve_path(path)
                policy = registry.get_policy(ns_name)
                if policy.allow_read:
                    final_inputs.append(path)
                else:
                    self._log.warning(f"Process '{process_name}' requested READ to Namespace '{ns_name}' but it is restricted by policy.")

            final_outputs = []
            for path in allowed_outputs:
                ns_name, _ = registry.resolve_path(path)
                policy = registry.get_policy(ns_name)
                if policy.allow_update or policy.allow_append or policy.allow_delete:
                    final_outputs.append(path)
                else:
                    self._log.warning(f"Process '{process_name}' requested WRITE to Namespace '{ns_name}' but it is restricted by policy.")
            
            # [Fix v3.1.2] Update instance whitelists to the filtered versions
            # This ensures nested guards (which inherit these) correctly respect policies.
            object.__setattr__(self, "_allowed_inputs", set(final_inputs))
            object.__setattr__(self, "_allowed_outputs", set(final_outputs))

            # Create the Rust heart of the guard
            self._inner = _RustContextGuard(
                target=target_obj,
                inputs=final_inputs,
                outputs=final_outputs,
                path_prefix=path_prefix,
                tx=transaction,
                is_admin=False,
                strict_guards=strict_guards,
            )

    def _check_zone_physics(self, path: str, mode: str) -> None:
        """[RFC-001 §5] Enforce Zone Physics at Python layer."""
        # Extract last segment for prefix check
        # path may be 'domain.const_config', 'domain.nested.const_value', etc.
        segments = path.replace("[", ".").replace("]", "").split(".")
        for segment in segments:
            # [RFC-001 §5] CONSTANT zone — unbreakable ceiling
            if segment.startswith("const_"):
                if mode in ("write", "append", "delete"):
                    # [RFC-001 §7] Check if an explicit Annotated override exists
                    # NOTE: If the user explicitly annotated a const_ field as Mutable,
                    # the override takes precedence over the const_ prefix.
                    # Check both exact path and parent path (for dict key access like domain.const_data[key])
                    has_override = False
                    try:
                        from theus.context import PYTHON_PHYSICS_OVERRIDES
                        import re
                        # Strip [key] suffixes to get the base field path
                        base_path = re.sub(r'\[.*?\]', '', path)
                        if path in PYTHON_PHYSICS_OVERRIDES or base_path in PYTHON_PHYSICS_OVERRIDES:
                            has_override = True
                    except Exception:
                        pass
                    if not has_override:
                        raise PermissionError(
                            f"Illegal {mode.capitalize()}: 'const_' field '{path}' is CONSTANT. "
                            "No process, including Admin, can mutate a CONSTANT field (RFC-001 §5)."
                        )
            # [RFC-001 Handbook §1.1] PRIVATE zone — hidden from non-admin
            if segment.startswith("internal_"):
                if mode == "read" and not self._local_is_admin:
                    # NOTE: Raise special sentinel to tell caller to return None.
                    raise _PrivateZoneReadAccess()

    def _is_allowed(self, path: str, mode: str = "read") -> bool:
        """[v3.2] Granular check for path access (supports wildcards).
        
        NOTE: This only enforces restrictions on paths belonging to REGISTERED namespaces.
        System paths (outbox, policy_id, etc.) are always allowed through to the Rust guard.
        """
        import fnmatch
        if self._local_is_admin: return True
        
        # Use getattr to avoid recursion in __getattr__
        inputs = getattr(self, "_allowed_inputs", None)
        outputs = getattr(self, "_allowed_outputs", None)
        
        # [v3.1.1 Legacy] If no whitelists provided (None), we are in permissive mode.
        if inputs is None and mode == "read": return True
        if outputs is None and mode == "write": return True
        
        # [RFC-002 KEY INSIGHT] Only enforce isolation for paths that belong to a registered namespace.
        # If the top-level segment of the path is NOT a registered namespace, allow through.
        from .context import NamespaceRegistry
        registry = NamespaceRegistry()
        
        norm_path = path.replace("[", ".").replace("]", "")
        top_level = norm_path.split(".")[0]
        
        if top_level not in registry._namespaces:
            # Not a registered namespace path → pass through freely to Rust guard.
            return True
        
        # --- PATH IS IN A REGISTERED NAMESPACE --- enforce whitelist ---
        all_patterns = (inputs or set()) | (outputs or set())
        
        if mode == "read":
            # READ DISCOVERY: allow if path matches any input OR any output sub-path
            if "*" in all_patterns: return True
            for pattern in all_patterns:
                norm_pattern = pattern.replace("[", ".").replace("]", "")
                if fnmatch.fnmatch(norm_path, norm_pattern): return True
                # Allow parent-path discovery (ctx.domain is needed to write ctx.domain.key)
                if norm_path.startswith(norm_pattern + "."): return True
                if norm_pattern.startswith(norm_path + "."): return True
            return False
            
        # WRITE MODE: strict check against outputs only
        targets = outputs
        if targets is None: return True
        if "*" in targets: return True
        for pattern in targets:
            norm_pattern = pattern.replace("[", ".").replace("]", "")
            if fnmatch.fnmatch(norm_path, norm_pattern): return True
            # Allow sub-path writes (writing domain.key.sub when domain.key is declared)
            if norm_path.startswith(norm_pattern + "."): return True
        return False

    @property
    def is_admin(self) -> bool:
        """[RFC-001] Check if this guard is in Admin (Bypass) mode."""
        return self._local_is_admin

    @property
    def is_proxy(self) -> bool:
        return True

    def _elevate(self, enabled: bool):
        """[RFC-001] Explicitly elevate/reset admin status on inner guard."""
        object.__setattr__(self, "_local_is_admin", enabled)
        
        # 1. Elevate the Rust heart (if it's a ContextGuard)
        if isinstance(self._inner, _RustContextGuard):
            if hasattr(self._inner, "_elevate"):
                try: self._inner._elevate(enabled)
                except (AttributeError, PermissionError): pass
            else:
                try: self._inner.is_admin = enabled
                except (AttributeError, PermissionError): pass
        
        # NOTE: We DO NOT aggressively propagate to native proxies here (e.g. setting 'capabilities')
        # because that triggers ContractViolationError if the proxy-path is not in outputs.
        # Instead, we use Parent-Level Overwrite in destructive methods (clear/pop/remove).

    def __getattr__(self, name: str) -> Any:
        # [RFC-001 §10] Block __dict__ access to prevent bypassing Zone Physics.
        # NOTE: On ContextGuard instances, __dict__ access from user code triggers
        # __getattr__ because ContextGuard has __slots__-like behavior through its
        # __init__ using object.__setattr__. This is a safe interception point.
        if name == "__dict__":
            raise PermissionError(
                "Direct access to '__dict__' is forbidden. "
                "Use the Context API to read/write fields safely."
            )
        # 1. Immediate bypass for whitelisted Python-side attributes
        if name in ("_inner", "_local_is_admin", "_log", "_elevate", "is_admin", "is_proxy", "_outbox", "_path_prefix", "_allowed_inputs", "_allowed_outputs", "_transaction", "_strict_guards", "_parent", "_name", "_target"):
            return object.__getattribute__(self, name)

        full_path = name if self._path_prefix == "" else f"{self._path_prefix}.{name}"
        # [RFC-001 §5] Zone physics check first (const_/internal_)
        try:
            self._check_zone_physics(full_path, "read")
        except _PrivateZoneReadAccess:
            return None  # internal_ field: return None silently for non-admin
        if not self._is_allowed(full_path, "read"):
             # For discovery, we allow 'domain' or 'global' prefixes even if not explicitly in inputs, 
             # provided a sub-path IS allowed. _is_allowed already handles this parent-path check.
             raise PermissionError(f"Illegal Read: Path '{full_path}' is restricted by Process Contract.")

        val = None
        # 2. Rust delegation
        try:
            val = getattr(self._inner, name) if self._inner is not None else None
            if val is None and self._target:
                 # Try target (Hybrid Bridge)
                 val = getattr(self._target, name, None)
        except RuntimeError as rt_err:
            # [v3.4] Transaction no longer leaks into data graph.
            # If RuntimeError occurs here, it is a genuine error — log and re-raise.
            import warnings
            warnings.warn(
                f"ContextGuard.__getattr__('{name}'): RuntimeError from Rust proxy — {rt_err}",
                RuntimeWarning, stacklevel=2
            )
            raise
        except AttributeError:
             # [RFC-002] Support attribute-style access for DICT proxies or items (e.g. state.domain.balance)
            if hasattr(self._inner, "__getitem__") and not name.startswith("_"):
                 try:
                     return self._inner[name]
                 except (KeyError, TypeError, AttributeError):
                     pass
             
            # [RFC-002] Dynamic Namespace Fallback
            # [RFC-002] Dynamic Namespace Fallback
            from .context import NamespaceRegistry
            if name in NamespaceRegistry()._namespaces:
                try:
                    # Reach into Rust Core: ProcessContext -> State -> Data
                    pc = self._inner._target
                    state_data = pc.state.data
                    val = state_data[name]
                    
                    full_path = name if self._path_prefix == "" else f"{self._path_prefix}.{name}"
                    
                    if isinstance(val, (dict, list)):
                        return ContextGuard(
                            target_obj=None,
                            allowed_inputs=self._allowed_inputs,
                            allowed_outputs=self._allowed_outputs,
                            path_prefix=full_path,
                            transaction=_current_tx.get(),
                            strict_guards=self._strict_guards,
                            process_name=self._log.extra.get("process_name", "Unknown"),
                            _inner=val,
                            parent=self,
                            name=name,
                        )
                    return val
                except Exception:
                    raise
            
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        except PermissionError as e:
            raise e
        
        if self._local_is_admin:
            # 1. Aggressive Propagate Elevation to Rust Proxy
            if hasattr(val, "_set_capabilities"):
                 try: val._set_capabilities(31)
                 except: pass
            else:
                 for attr in ["capabilities", "_capabilities", "caps"]:
                      if hasattr(val, attr):
                           try: setattr(val, attr, 31)
                           except: pass

            # 2. Return elevated wrapper
            if not isinstance(val, ContextGuard) and not isinstance(val, (int, float, str, bool, type(None))):
                 # RECONCILE INNER PROXY (Hybrid Bridge)
                 sub_inner = getattr(val, "_theus_proxy", None)
                 new_guard = ContextGuard(
                    target_obj=val,
                    allowed_inputs=self._allowed_inputs,
                    allowed_outputs=self._allowed_outputs,
                    _inner=sub_inner or val, # Use proxy if available, else native
                    process_name=self._log.extra.get("process_name", "Unknown"),
                    transaction=_current_tx.get(),
                    parent=self,
                    name=name,
                )
                 new_guard._elevate(True)
                 return new_guard
        
        # 4. Nested Guard wrapping (Normal flow)
        if isinstance(val, _RustContextGuard) or (hasattr(val, "is_proxy") and getattr(val, "is_proxy")()):
            sub_target = None
            if self._target is not None:
                sub_target = getattr(self._target, name, None)
                if sub_target is None and hasattr(self._target, "get"):
                    sub_target = self._target.get(name)

            return ContextGuard(
                target_obj=sub_target,
                allowed_inputs=self._allowed_inputs,
                allowed_outputs=self._allowed_outputs,
                path_prefix=full_path,
                _inner=val,
                process_name=self._log.extra.get("process_name", "Unknown"),
                transaction=_current_tx.get(),
                parent=self,
                name=name,
            )
        return val

    def __getitem__(self, key: Any) -> Any:
        full_path = str(key) if self._path_prefix == "" else f"{self._path_prefix}[{key}]"
        if isinstance(key, str) and not self._is_allowed(full_path, "read"):
             raise PermissionError(f"Illegal Read: Path '{full_path}' is restricted by Process Contract.")

        val = None
        try:
            val = self._inner[key]
        except RuntimeError as rt_err:
            # [v3.4] Transaction no longer leaks into data graph.
            # If RuntimeError occurs here, it is a genuine error — log and re-raise.
            import warnings
            warnings.warn(
                f"ContextGuard.__getitem__('{key}'): RuntimeError from Rust proxy — {rt_err}",
                RuntimeWarning, stacklevel=2
            )
            raise
        except (PermissionError, AttributeError, KeyError, IndexError, TypeError) as e:
            # [RFC-002] Dynamic Namespace Fallback for Item Access
            if isinstance(key, str):
                from .context import NamespaceRegistry
                if key in NamespaceRegistry()._namespaces:
                    try:
                         # Attempt to reach into Rust Core for Namespace resolution
                         pc = getattr(self._inner, "_target", None)
                         if pc:
                            state_data = pc.state.data
                            val = state_data[key]
                            
                            full_path = key if self._path_prefix == "" else f"{self._path_prefix}.{key}"
                            
                            if isinstance(val, (dict, list)):
                                return ContextGuard(
                                    target_obj=None,
                                    allowed_inputs=self._allowed_inputs,
                                    allowed_outputs=self._allowed_outputs,
                                    path_prefix=full_path,
                                    transaction=_current_tx.get(),
                                    strict_guards=self._strict_guards,
                                    process_name=self._log.extra.get("process_name", "Unknown"),
                                    _inner=val,
                                    parent=self,
                                    name=key,
                                )
                            return val
                    except Exception:
                        pass
            raise e

        if self._local_is_admin:
            if not isinstance(val, ContextGuard) and not isinstance(val, (int, float, str, bool, type(None))):
                 sub_inner = getattr(val, "_theus_proxy", None)
                 new_guard = ContextGuard(
                    target_obj=val,
                    allowed_inputs=self._allowed_inputs,
                    allowed_outputs=self._allowed_outputs,
                    _inner=sub_inner or val,
                    process_name=self._log.extra.get("process_name", "Unknown"),
                    transaction=_current_tx.get(),
                    parent=self,
                    name=key,
                )
                 new_guard._elevate(True)
                 return new_guard

        # 4. Nested Guard wrapping (Normal flow)
        if isinstance(val, _RustContextGuard) or (hasattr(val, "is_proxy") and getattr(val, "is_proxy")()):
            sub_target = None
            if self._target is not None:
                if hasattr(self._target, "__getitem__"):
                    try:
                        sub_target = self._target[key]
                    except (KeyError, TypeError):
                        pass
                if sub_target is None and isinstance(key, str):
                    if hasattr(self._target, "get"):
                        sub_target = self._target.get(key)
                    if sub_target is None:
                        sub_target = getattr(self._target, key, None)

            return ContextGuard(
                target_obj=sub_target,
                allowed_inputs=self._allowed_inputs,
                allowed_outputs=self._allowed_outputs,
                path_prefix=full_path,
                _inner=val,
                process_name=self._log.extra.get("process_name", "Unknown"),
                transaction=_current_tx.get(),
                parent=self,
                name=key,
            )
        return val

    # [RFC-001] SHADOW METHODS FOR ADMIN BYPASS + ZONE PHYSICS ENFORCEMENT
    # We must intercept these methods because they do NOT go through __setattr__.
    # The flow: ctx.domain.const_list.append(x)
    #   -> __getattr__("const_list") returns nested ContextGuard with path_prefix="domain.const_list"
    #   -> .append(x) calls THIS method (not __setattr__)
    # So we enforce zone physics here too.

    def append(self, *args, **kwargs):
        """[RFC-001 §5] Check CONSTANT zone before append."""
        self._check_zone_physics(self._path_prefix or "?", "append")
        if hasattr(self._inner, "append"):
            return self._inner.append(*args, **kwargs)

    def extend(self, *args, **kwargs):
        """[RFC-001 §5] Check CONSTANT zone before extend."""
        self._check_zone_physics(self._path_prefix or "?", "append")
        if hasattr(self._inner, "extend"):
            return self._inner.extend(*args, **kwargs)

    def insert(self, *args, **kwargs):
        """[RFC-001 §5] Check CONSTANT zone before insert."""
        self._check_zone_physics(self._path_prefix or "?", "append")
        if hasattr(self._inner, "insert"):
            return self._inner.insert(*args, **kwargs)

    def clear(self):
        """[RFC-001 §5] Check CONSTANT zone before clear (delete)."""
        self._check_zone_physics(self._path_prefix or "?", "delete")
        if hasattr(self._inner, "clear"):
            try:
                return self._inner.clear()
            except (PermissionError, AttributeError) as e:
                if self._local_is_admin:
                     # FORCE CLEAR via parent-level assignment
                     try:
                         if self._parent:
                             # Overwrite on parent (bypass native child clear)
                             if hasattr(self._parent, "__setitem__"):
                                 self._parent[self._name] = []
                             else:
                                 setattr(self._parent, self._name, [])
                             return None
                     except: pass
                raise e
        return None

    def pop(self, *args, **kwargs):
        """[RFC-001 §5] Check CONSTANT zone before pop (delete)."""
        self._check_zone_physics(self._path_prefix or "?", "delete")
        if hasattr(self._inner, "pop"):
            try:
                return self._inner.pop(*args, **kwargs)
            except (PermissionError, AttributeError) as e:
                if self._local_is_admin:
                     # Emulate pop via slice deletion
                     try:
                         if len(args) == 0:
                              val = self._inner[-1]
                              del self._inner[-1]
                         else:
                              val = self._inner[args[0]]
                              del self._inner[args[0]]
                         return val
                     except: pass
                raise e
        return None

    def remove(self, *args, **kwargs):
        """[RFC-001 §5] Check CONSTANT zone before remove (delete)."""
        self._check_zone_physics(self._path_prefix or "?", "delete")
        if hasattr(self._inner, "remove"):
            try:
                return self._inner.remove(*args, **kwargs)
            except (PermissionError, AttributeError) as e:
                if self._local_is_admin:
                     # Emulate remove via index/del
                     try:
                         idx = self._inner.index(args[0])
                         del self._inner[idx]
                         return None
                     except: pass
                raise e
        return None

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_inner", "_local_is_admin", "_log", "_outbox", "_path_prefix", "_allowed_inputs", "_allowed_outputs", "_transaction", "_strict_guards", "_parent", "_name", "_target"):
            object.__setattr__(self, name, value)
            return

        full_path = name if self._path_prefix == "" else f"{self._path_prefix}.{name}"
        # [RFC-001 §5] Zone physics check (const_ blocked even for admin)
        self._check_zone_physics(full_path, "write")
        if not self._is_allowed(full_path, "write"):
             raise PermissionError(f"Illegal Write: Path '{full_path}' is restricted by Process Contract.")

        # Unwrap Python ContextGuard before passing to Rust (Deep Unwrap)
        def _deep_unwrap(v):
            if isinstance(v, ContextGuard):
                return _deep_unwrap(v._inner)
            if isinstance(v, dict):
                return {k: _deep_unwrap(sub_v) for k, sub_v in v.items()}
            if isinstance(v, list):
                 return [_deep_unwrap(sub_v) for sub_v in v]
            if isinstance(v, tuple):
                 return tuple(_deep_unwrap(sub_v) for sub_v in v)
            return v
            
        value = _deep_unwrap(value)
            
        # Support attribute-style access for dict keys
        if isinstance(self._inner, dict):
            self._inner[name] = value
        else:
            setattr(self._inner, name, value)

    def __setitem__(self, key: Any, value: Any) -> None:
        full_path = str(key) if self._path_prefix == "" else f"{self._path_prefix}[{key}]"
        # [RFC-001 §5] Zone physics check (const_ blocked even for admin)
        if isinstance(key, str):
            self._check_zone_physics(full_path, "write")
        if isinstance(key, str) and not self._is_allowed(full_path, "write"):
             raise PermissionError(f"Illegal Write: Path '{full_path}' is restricted by Process Contract.")

        def _deep_unwrap(v):
            if isinstance(v, ContextGuard):
                return _deep_unwrap(v._inner)
            if isinstance(v, dict):
                return {k: _deep_unwrap(sub_v) for k, sub_v in v.items()}
            if isinstance(v, list):
                 return [_deep_unwrap(sub_v) for sub_v in v]
            if isinstance(v, tuple):
                 return tuple(_deep_unwrap(sub_v) for sub_v in v)
            return v
        value = _deep_unwrap(value)
        
        try:
            self._inner[key] = value
        except (TypeError, AttributeError):
            # Support attribute-style write if not subscriptable
            if isinstance(key, str):
                setattr(self._inner, key, value)
            else:
                raise

    def __iter__(self):
        return iter(self._inner)

    def __contains__(self, item):
        return item in self._inner

    def __len__(self):
        return len(self._inner)

    def __repr__(self):
        return f"<ContextGuard wrapping {repr(self._inner)} admin={self._local_is_admin}>"
