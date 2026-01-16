try:
    from theus_core import AuditSystem as AuditSystemRust, AuditRecipe, AuditBlockError
except ImportError:
    class AuditRecipe:
        def __init__(self, threshold_max, reset_on_success): pass
    class AuditSystemRust:
        def __init__(self, recipe): pass
    class AuditBlockError(Exception): pass

class AuditSystem(AuditSystemRust):
    pass

__all__ = ["AuditSystem", "AuditRecipe", "AuditBlockError"]
