from .engine import TheusEngine
from .contracts import process, ContractViolationError
# context module might be broken too if I touched it? (I didn't).
# But locks module?
# Let's keep minimal valid imports.


# Conditional import for Sub-Interpreter support (Theus v3.2)
try:
    from theus_core import SignalHub, SignalReceiver, SchemaViolationError
    CORE_AVAILABLE = True
except ImportError:
    # This happens when running in a sub-interpreter if the extension 
    # doesn't support multi-phase initialization yet.
    # We allow the import to proceed so pure-Python parallel tasks can run.
    CORE_AVAILABLE = False
    SignalHub, SignalReceiver, SchemaViolationError = None, None, None

__version__ = "3.0.21"
