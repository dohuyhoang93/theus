
from typing import Any

def get_attr(ctx: Any, path: str, default: Any = None) -> Any:
    """Safe attribute accessor for Hybrid Context (Dict or Object)."""
    # 1. Resolve Root (domain/global)
    parts = path.split('.')
    root_name = parts[0]
    
    # Access root from proxy or object
    has_attr = False
    try:
         has_attr = hasattr(ctx, root_name)
    except (KeyError, AttributeError):
         has_attr = False

    if has_attr:
        root = getattr(ctx, root_name)
    elif hasattr(ctx, 'data') and isinstance(ctx.data, dict):
        root = ctx.data.get(root_name)
    else:
        # print(f"DEBUG: Root {root_name} not found in ctx {type(ctx)}")
        return default
        
    if root is None:
        return default
        
    # 2. Traverse logic
    current = root
    for part in parts[1:]:
        # Helper for proxy objects that might raise KeyError on attribute check
        has_attr = False
        try:
             has_attr = hasattr(current, part)
        except (KeyError, AttributeError):
             has_attr = False
             
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        elif has_attr:
             current = getattr(current, part)
        else:
             return default
             
    return current

def set_attr(ctx: Any, path: str, value: Any):
    """Safe attribute setter for Hybrid Context."""
    parts = path.split('.')
    root_name = parts[0]
    
    # Access root
    has_attr = False
    try:
         has_attr = hasattr(ctx, root_name)
    except (KeyError, AttributeError):
         has_attr = False

    if has_attr:
        root = getattr(ctx, root_name)
    elif hasattr(ctx, 'data') and isinstance(ctx.data, dict):
        root = ctx.data.get(root_name)
    else:
        # If root missing, we can't set.
        return
        
    current = root
    # Traverse to parent
    for part in parts[1:-1]:
        # Helper for proxy objects that might raise KeyError on attribute check
        has_attr_part = False
        try:
             has_attr_part = hasattr(current, part)
        except (KeyError, AttributeError):
             has_attr_part = False

        if isinstance(current, dict):
            current = current.setdefault(part, {})
        elif has_attr_part:
            current = getattr(current, part)
        else:
            return # Cannot traverse
            
    # Set leaf
    last_part = parts[-1]
    
    has_attr_leaf = False
    try:
         has_attr_leaf = hasattr(current, last_part)
    except (KeyError, AttributeError):
         has_attr_leaf = False

    has_data_attr = False
    try:
        has_data_attr = hasattr(current, 'data')
    except (KeyError, AttributeError):
        has_data_attr = False
        
    # Try dict-like access first
    if isinstance(current, dict) or (hasattr(current, '__setitem__') and hasattr(current, '__getitem__')):
        try:
            current[last_part] = value
            return
        except Exception:
             # Proxy might demand .update()
             has_update = False
             try:
                 has_update = hasattr(current, 'update')
             except Exception:
                 pass
                 
             if has_update:
                 current.update({last_part: value})
                 return
             # Otherwise continue to alternatives
            
    if has_attr_leaf:
        setattr(current, last_part, value)
    elif has_data_attr and isinstance(current.data, dict): # Handle proxy wrapper case?
         current.data[last_part] = value
         
