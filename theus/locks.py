
import logging
from contextlib import contextmanager
from typing import Literal

logger = logging.getLogger("POP.LockManager")

class LockViolationError(Exception):
    """Raised when a Context modification occurs outside of a Transaction in Strict Mode."""
    pass

class LockManager:
    """
    Manages the Write Permission of the Context.
    Follows the Rust Principle: 
    - Unsafe code runs with WARNING (Default).
    - Unsafe code fails with ERROR (Strict Mode).
    """
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self._locked = True # Default is Locked (Secure by Default)
        
    def validate_write(self, attr_name: str, target_obj: object):
        """
        Called by Context.__setattr__ to verify permission.
        """
        if not self._locked:
            return # Safe to write (Inside Transaction)
            
        # If Locked: Violation!
        msg = f"UNSAFE MUTATION: Attempting to modify '{attr_name}' on '{type(target_obj).__name__}' outside of a Transaction."
        hint = "  Hint: Use 'with engine.edit():' or wrap code in a Process."
        
        full_msg = f"{msg}\n{hint}"
        
        if self.strict_mode:
            logger.error(full_msg)
            raise LockViolationError(full_msg)
        else:
            # Rust-style Warning
            logger.warning(full_msg)
            
    @contextmanager
    def unlock(self):
        """
        Context Manager to temporarily unlock safety.
        Used by POPEngine during Process execution or `edit()`.
        """
        prev_state = self._locked
        self._locked = False
        try:
            yield
        finally:
            self._locked = prev_state
