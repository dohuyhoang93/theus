from typing import Any, List, Dict, Union, MutableSequence, MutableMapping
from .delta import Transaction, DeltaEntry
from .contracts import ContractViolationError

class TrackedList(MutableSequence):
    """
    A smart wrapper around a list that logs all mutations to a Transaction.
    It operates on a 'Shadow List', ensuring isolation.
    """
    def __init__(self, shadow_list: List, transaction: Transaction, path: str):
        self._data = shadow_list
        self._tx = transaction
        self._path = path

    # --- MutableSequence Abstract Methods ---
    # --- MutableSequence Abstract Methods ---
    def __getitem__(self, index):
        val = self._data[index]
        # Recursively wrap List/Dict
        if isinstance(val, (list, dict)):
            # 1. Get/Create Shadow for the child
            shadow_child = self._tx.get_shadow(val)
            
            # 2. Update Link (Lazy Deepening)
            if shadow_child is not val:
                 self._data[index] = shadow_child
                 
            # 3. Return Wrapped
            child_path = f"{self._path}[{index}]"
            if isinstance(shadow_child, list):
                return TrackedList(shadow_child, self._tx, child_path)
            elif isinstance(shadow_child, dict):
                return TrackedDict(shadow_child, self._tx, child_path)
                
        return val

    def __setitem__(self, index, value):
        old_val = self._data[index]
        self._data[index] = value
        
        # Log Logic: path[index]
        entry_path = f"{self._path}[{index}]"
        # Rust Transaction.log(path, op, value, old_value, target, key)
        self._tx.log(entry_path, "SET", value, old_val, None, None) 

    def __delitem__(self, index):
        old_val = self._data[index]
        del self._data[index]
        
        entry_path = f"{self._path}[{index}]"
        self._tx.log(entry_path, "REMOVE", None, old_val, None, None)

    def __len__(self):
        return len(self._data)

    def insert(self, index, value):
        self._data.insert(index, value)
        # Log INSERT is complex for paths, but we simplify to "INSERT" op
        self._tx.log(f"{self._path}", "INSERT", (index, value))

    # --- Optimizations / Overrides ---
    def append(self, value):
        self._data.append(value)
        self._tx.log(self._path, "APPEND", value)
        
    def extend(self, values):
        self._data.extend(values)
        self._tx.log(self._path, "EXTEND", values)
        
    def pop(self, index=-1):
        val = self._data.pop(index)
        self._tx.log(self._path, "POP", index, val)
        return val
        
    def __repr__(self):
        return repr(self._data)
        
    def __str__(self):
        return str(self._data)


class TrackedDict(MutableMapping):
    """
    A smart wrapper around a dict that logs all mutations.
    """
    def __init__(self, shadow_dict: Dict, transaction: Any, path: str):
        self._data = shadow_dict
        self._tx = transaction
        self._path = path

    def __getitem__(self, key):
        val = self._data[key]
        if isinstance(val, (list, dict)):
            shadow_child = self._tx.get_shadow(val)
            
            if shadow_child is not val:
                 self._data[key] = shadow_child
            
            entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
            
            if isinstance(shadow_child, list):
                return TrackedList(shadow_child, self._tx, entry_path)
            elif isinstance(shadow_child, dict):
                return TrackedDict(shadow_child, self._tx, entry_path)
                
        return val

    def __setitem__(self, key, value):
        old_val = self._data.get(key)
        self._data[key] = value
        
        # Let's use dot for string keys, bracket for others? 
        # For simplicity in POP (which implies JSON-like context), keys are usually strings.
        entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
        
        # op = "UPDATE" if old_val is not None else "ADD" # This is now handled by the SET operation itself
        self._tx.log(entry_path, "SET", value, old_val, None, None)

    def __delitem__(self, key):
        old_val = self._data[key]
        del self._data[key]
        
        entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
        self._tx.log(DeltaEntry(entry_path, "REMOVE", None, old_val))

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)
        
    def __repr__(self):
        return repr(self._data)

class FrozenList(TrackedList):
    """
    A read-only wrapper around a list. Raises ContractViolationError on any mutation.
    """
    def __init__(self, shadow_list: List, transaction: Transaction, path: str):
        super().__init__(shadow_list, transaction, path)

    def __setitem__(self, index, value):
        raise ContractViolationError(f"Immutable Violation: Cannot modify read-only input '{self._path}[{index}]'.")

    def __delitem__(self, index):
        raise ContractViolationError(f"Immutable Violation: Cannot delete from read-only input '{self._path}[{index}]'.")

    def insert(self, index, value):
        raise ContractViolationError(f"Immutable Violation: Cannot insert into read-only input '{self._path}'.")

    def append(self, value):
        raise ContractViolationError(f"Immutable Violation: Cannot append to read-only input '{self._path}'.")

    def extend(self, values):
        raise ContractViolationError(f"Immutable Violation: Cannot extend read-only input '{self._path}'.")

    def pop(self, index=-1):
        raise ContractViolationError(f"Immutable Violation: Cannot pop from read-only input '{self._path}'.")
    
    def __getitem__(self, index):
        # Allow reading, but recursively freeze children
        val = self._data[index]
        if isinstance(val, (list, dict)):
            # Even for frozen, we get a shadow to ensure we are reading consistent snapshot?
            # Yes, standard shadowing logic applies for consistency.
            shadow_child = self._tx.get_shadow(val)
            
            # Recursive Freeze
            child_path = f"{self._path}[{index}]"
            if isinstance(shadow_child, list):
                return FrozenList(shadow_child, self._tx, child_path)
            elif isinstance(shadow_child, dict):
                return FrozenDict(shadow_child, self._tx, child_path)
        return val


class FrozenDict(TrackedDict):
    """
    A read-only wrapper around a dict. Raises ContractViolationError on any mutation.
    """
    def __init__(self, shadow_dict: Dict, transaction: Transaction, path: str):
        super().__init__(shadow_dict, transaction, path)

    def __setitem__(self, key, value):
        entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
        raise ContractViolationError(f"Immutable Violation: Cannot modify read-only input '{entry_path}'.")

    def __delitem__(self, key):
        entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
        raise ContractViolationError(f"Immutable Violation: Cannot delete from read-only input '{entry_path}'.")

    def pop(self, key, default=None):
        entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
        raise ContractViolationError(f"Immutable Violation: Cannot pop from read-only input '{entry_path}'.")

    def popitem(self):
        raise ContractViolationError(f"Immutable Violation: Cannot popitem from read-only input '{self._path}'.")

    def clear(self):
        raise ContractViolationError(f"Immutable Violation: Cannot clear read-only input '{self._path}'.")

    def update(self, *args, **kwargs):
        raise ContractViolationError(f"Immutable Violation: Cannot update read-only input '{self._path}'.")

    def __getitem__(self, key):
        # Allow reading, but recursively freeze children
        val = self._data[key]
        if isinstance(val, (list, dict)):
            shadow_child = self._tx.get_shadow(val)
            
            entry_path = f"{self._path}.{key}" if isinstance(key, str) else f"{self._path}[{key}]"
            
            if isinstance(shadow_child, list):
                return FrozenList(shadow_child, self._tx, entry_path)
            elif isinstance(shadow_child, dict):
                return FrozenDict(shadow_child, self._tx, entry_path)
        return val
