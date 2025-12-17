from typing import Any, Set, Optional
from .contracts import ContractViolationError
from .delta import Transaction, DeltaEntry
from .structures import TrackedList, TrackedDict, FrozenList, FrozenDict

class ContextGuard:
    """
    A runtime proxy that enforces POP Contracts (Read/Write permissions)
    AND facilitates Transactional Mutation (Delta Logging).
    """
    def __init__(self, target_obj: Any, allowed_inputs: Set[str], allowed_outputs: Set[str], path_prefix: str = "", transaction: Optional[Transaction] = None):
        # Use object.__setattr__ to avoid recursion during init
        object.__setattr__(self, "_target_obj", target_obj)
        object.__setattr__(self, "_allowed_inputs", allowed_inputs)
        object.__setattr__(self, "_allowed_outputs", allowed_outputs)
        object.__setattr__(self, "_path_prefix", path_prefix)
        object.__setattr__(self, "_transaction", transaction)

    def __getattr__(self, name: str):
        # 1. System/Magic Attribute Bypass
        # Allow Python internal attributes (e.g. __class__, _pytest_fixture)
        if name.startswith("_"):
             return getattr(self._target_obj, name)

        # 2. Navigation Logic (Layer Containers)
        # We assume accessing a Layer Container (e.g. domain_ctx) is always allowed/safe
        # so we can traverse deeper to check the actual leaf variable.
        if name.endswith("_ctx"):
             val = getattr(self._target_obj, name)
             # Logic: layer name inference. 
             # domain_ctx -> "domain"
             next_prefix = name.replace("_ctx", "")
             # Pass transaction down
             return ContextGuard(val, self._allowed_inputs, self._allowed_outputs, next_prefix, self._transaction)

        # 3. Leaf / Primitive Attribute Logic
        full_path = f"{self._path_prefix}.{name}" if self._path_prefix else name
            
        # READ GUARD
        # Rule: Full path must be in inputs OR a parent path is in inputs
        parts = full_path.split('.')
        parent_paths = ['.'.join(parts[:i]) for i in range(1, len(parts))]
        
        is_allowed = (
            full_path in self._allowed_inputs or 
            any(p in self._allowed_inputs for p in parent_paths) or
            # Traversal Fix: Allow if this path leads to an allowed leaf (Prefix)
            any(inp.startswith(full_path + ".") for inp in self._allowed_inputs)
        )
        
        if not is_allowed:
             raise ContractViolationError(
                f"Illegal Read Violation: Process attempted to read '{full_path}' "
                f"but it was not declared in inputs=[...]."
            )
        
        # Safe to read now
        # TRANSACTION INTEGRATION:
        # If we have a transaction, we should return a Shadow object or Tracked Wrapper
        val = getattr(self._target_obj, name)
        
        if self._transaction:
            # Check if this specific leaf path is declared as Output (Writeable)
            # Logic: If it's in Outputs, it's Mutable. If it's only in Inputs, it's Immutable.
            # CAUTION: 'full_path' might be a parent of the output. 
            # e.g. full_path="domain.list", output="domain.list" -> Mutable.
            # e.g. full_path="domain.list", output="domain.list[0]" -> Mutable (Partial).
            
            is_writeable = (
                full_path in self._allowed_outputs or
                # Parent of an allowed output? (e.g. accessing list to write into it)
                any(out.startswith(full_path + ".") or out.startswith(full_path + "[") for out in self._allowed_outputs)
            )

            # Get or Create Shadow
            shadow = self._transaction.get_shadow(val)
            
            # Wrap based on permissions
            if isinstance(shadow, list):
                if is_writeable:
                    return TrackedList(shadow, self._transaction, full_path)
                else:
                    return FrozenList(shadow, self._transaction, full_path)

            elif isinstance(shadow, dict):
                if is_writeable:
                    return TrackedDict(shadow, self._transaction, full_path)
                else:
                    return FrozenDict(shadow, self._transaction, full_path)
            else:
                return shadow
        
        return val

    def __setattr__(self, name: str, value: Any):
        full_path = f"{self._path_prefix}.{name}" if self._path_prefix else name
            
        # WRITE GUARD
        if full_path not in self._allowed_outputs:
            raise ContractViolationError(
                f"Illegal Write Violation: Process attempted to modify '{full_path}' "
                f"but it was not declared in outputs=[...]."
            )
            
        # TRANSACTION INTEGRATION
        if self._transaction:
             old_val = getattr(self._target_obj, name, None)
             # Log the SET operation (The commit phase will apply it)
             # Note: For primitives, we must assume that 'commit' will set it on the target object.
             # Wait, if we log it, we must ALSO update the Shadow so the process sees it?
             # Yes. But since we don't have a "Shadow Target Object" (we only shadow lists/dicts),
             # we are in a tricky spot for scalar updates like `ctx.domain.x = 5`.
             
             # Problem: `ctx.domain` IS `_target_obj`. It is usually a Dataclass instance.
             # If we don't update `_target_obj` now, `getattr` later will return old value.
             # Solution: `Transaction` must cache/shadow the PARENT object too?
             # OR: strict "Last Write Wins": We update `_target_obj` IN-PLACE regarding the Shadow?
             # But `_target_obj` IS the Real Context Layer (e.g. DomainContext).
             
             # Re-read Design: "Proxy writes to _delta_log... If Process success, Apply."
             # This implies `getattr` must look at `_delta_log`? Expensive.
             # Better: We create a Shadow Context Layer at valid checkpoints?
             
             # SIMPLIFICATION for Phase 2:
             # We allow modifying the REAL object for scalars (since we can't easily shadow a dataclass without cloning it).
             # BUT we log the OLD value for Rollback.
             # This is "Optimistic Concurrency" or "In-place + Undo Log".
             # For List/Dict, we use Shadow Copy + TrackedWrapper.
             
             # So:
             # 2. Perform setattr on REAL object.
             
             self._transaction.log(DeltaEntry(full_path, "SET", value, old_val, target=self._target_obj, key=name))
             
             # AUTO-UNWRAP PROXY (Zombie Proxy Fix)
             # If we are assigning a TrackedList/Dict, we must store the Shadow Data, not the Wrapper.
             if isinstance(value, (TrackedList, TrackedDict)):
                 # Assign the _data (Shadow Object)
                 setattr(self._target_obj, name, value._data)
             else:
                 setattr(self._target_obj, name, value)
        else:
             setattr(self._target_obj, name, value)
