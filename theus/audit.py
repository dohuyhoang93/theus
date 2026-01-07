import logging

logger = logging.getLogger("POP_AUDIT")

class AuditError(Exception):
    """Base for audit failures."""
    pass

class AuditInterlockError(AuditError):
    """Level S/A violation -> Hard Crash (Stop Workflow)."""
    pass

class AuditBlockError(AuditError):
    """Level B violation -> Soft Block (Rollback Transaction)."""
    pass

# Deprecated Shells ensuring backward compatibility for imports
# but warning that logic has moved to Rust.

class AuditTracker:
    def __init__(self):
        pass

class AuditPolicy:
    def __init__(self, recipe):
        pass
    def evaluate(self, *args, **kwargs):
        pass

class ContextAuditor:
    def __init__(self, recipe):
        pass
    def audit_input(self, *args, **kwargs):
        pass
    def audit_output(self, *args, **kwargs):
        pass
