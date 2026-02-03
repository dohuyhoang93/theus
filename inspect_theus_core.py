import sys
import inspect

try:
    import theus_core
    print(f"theus_core file: {theus_core.__file__}")
    from theus_core import AuditSystem
    print(f"AuditSystem source: {inspect.getsourcefile(AuditSystem)}")
    print(f"AuditSystem lines: {inspect.getsourcelines(AuditSystem)}")
except Exception as e:
    print(f"Error: {e}")
    # Check if there is a 'src' fallback
    import os
    print(f"CWD: {os.getcwd()}")
    print("Listing locals:")
    for m in sys.modules:
        if 'theus' in m:
            print(f"  {m}: {sys.modules[m]}")
