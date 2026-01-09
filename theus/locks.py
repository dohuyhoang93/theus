
import logging
import threading
from contextlib import contextmanager
from typing import Literal, Optional

logger = logging.getLogger("Theus.LockManager")

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
    LockViolationError = LockViolationError # Expose for consistent import

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self._mutex = threading.Lock() # Protects the state
        self._writer_thread_id: Optional[int] = None
        
    def validate_write(self, attr_name: str, target_obj: object):
        """
        Called by Context.__setattr__ to verify permission.
        Thread-Safe: Only the thread that acquired the 'unlock' (Writer) can write.
        """
        current_id = threading.get_ident()
        
        # Check if Current Thread is the Active Writer
        is_owner = (self._writer_thread_id == current_id)
        
        if is_owner:
            return # Safe to write (Authorized Writer)
            
        # If not owner: Violation!
        msg = f"UNSAFE MUTATION: Thread {current_id} attempted to modify '{attr_name}' but Writer is {self._writer_thread_id or 'None'}."
        hint = "  Hint: Use 'with engine.edit():' or run within a Process."
        
        full_msg = f"{msg}\n{hint}"
        
        if self.strict_mode:
            logger.error(full_msg)
            raise LockViolationError(full_msg)
        else:
            # Rust-style Warning -> Silent for Training Performance
            # Switched to DEBUG to avoid spamming audit logs in non-strict mode
            logger.debug(full_msg)
            
    @contextmanager
    def unlock(self):
        """
        Thread-Safe Write Lock (Mutex).
        Acquires exclusive write access for the current thread.
        """
        # Block until we can acquire the mutex (Exclusive Write)
        with self._mutex:
            current_id = threading.get_ident()
            self._writer_thread_id = current_id
            try:
                yield
            finally:
                self._writer_thread_id = None
