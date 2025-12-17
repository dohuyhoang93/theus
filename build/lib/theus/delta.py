from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional, Union
import copy

@dataclass
class DeltaEntry:
    """
    Represent a single atomic change in the system.
    """
    path: str           # e.g. "domain.q_table", "domain.list[0]"
    op: str             # "SET", "APPEND", "EXTEND", "POP", "REMOVE", "CLEAR", "UPDATE"
    value: Any = None   # The new value (for SET, APPEND) or argument
    old_value: Any = None # The previous value (for Undo/Rollback)
    target: Any = None    # Reference to the object being modified (Transient, for Rollback)
    key: Any = None       # Attribute name or Index (Transient, for Rollback)

class Transaction:
    # ... (init and shadow cache stay same) ...
    def __init__(self, system_ctx_root: Any):
        self.root = system_ctx_root
        self.delta_log: List[DeltaEntry] = []
        self._shadow_cache: Dict[int, tuple] = {}
        self._shadow_ids: set = set() # Track IDs of created shadows

    def log(self, entry: DeltaEntry):
        self.delta_log.append(entry)
        
    def get_shadow(self, original_obj: Any) -> Any:
        obj_id = id(original_obj)
        
        # 1. Check if it's already a Shadow
        if obj_id in self._shadow_ids:
            return original_obj
            
        # 2. Check cache (Standard consistency)
        if obj_id in self._shadow_cache:
            return self._shadow_cache[obj_id][1]
        
        # 3. Create New Shadow
        if isinstance(original_obj, list):
            shadow = original_obj.copy()
        elif isinstance(original_obj, dict):
            shadow = original_obj.copy()
        elif isinstance(original_obj, tuple):
             shadow = tuple(self.get_shadow(x) for x in original_obj)
        else:
            # Generic Copy (Safety for Custom Objects/Dataclasses)
            # If it's a scalar (int, str), copy() returns self.
            # If it's a mutable object, it returns a shallow copy.
            try:
                import copy
                shadow = copy.copy(original_obj)
            except Exception:
                shadow = original_obj # Fallback for bizarre types
            
        self._shadow_cache[obj_id] = (original_obj, shadow)
        self._shadow_ids.add(id(shadow)) # Mark as shadow
        return shadow

    def commit(self):
        """
        Apply all Deltas/Shadows to the actual Root Context.
        For Mutable Shadows (List/Dict): Replace content of original with shadow.
        For Scalars: They were updated in-place (Optimistic), so we do nothing.
        """
        # 1. Apply Shadows back to Originals
        for original, shadow in self._shadow_cache.values():
            if original is shadow:
                continue
                
            if isinstance(original, list):
                original[:] = shadow # Replace content
            elif isinstance(original, dict):
                original.clear()
                original.update(shadow) # Replace content
            else:
                # Generic Object Sync (e.g. Dataclasses)
                # Since shadow is a shallow copy, we need to sync attributes back.
                try:
                    original.__dict__.update(shadow.__dict__)
                except AttributeError:
                    # Object has no __dict__ (e.g. slots, built-ins like sets), can't easily sync via copy.
                    # For V2 MVP we warn or ignore. 
                    pass
                
    def rollback(self):
        """
        Discard changes.
        For Scalars (Optimistic Write): Revert using logs in REVERSE order.
        For Shadows: Just discard them (Original was untouched).
        """
        # Revert Optimistic Writes
        for entry in reversed(self.delta_log):
            if entry.op == "SET" and entry.target is not None:
                # Revert attribute or item set
                if isinstance(entry.key, str): # Attribute
                    setattr(entry.target, entry.key, entry.old_value)
                else: # Index/Key? Usually SET is for attributes in guards.py
                    # Structures.py handles Lists differently (Shadows).
                    pass
        
        self.delta_log.clear()
        self._shadow_cache.clear()

