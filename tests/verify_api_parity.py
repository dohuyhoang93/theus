import unittest
import inspect
from typing import get_type_hints

import theus.engine
import theus_core

class TestAPIParity(unittest.TestCase):
    """
    Defense Layer: Ensures Python Wrappers match Rust Core signatures correctly.
    Prevents INC-015 (Missing Parameter) from happening again.
    """

    def test_theus_engine_parity(self):
        py_cls = theus.engine.TheusEngine
        rust_cls = theus_core.TheusEngine
        
        print("\n[Parity Check] Comparing TheusEngine Python Wrapper vs Rust Core...")

        # 1. Get list of methods in Rust Core (The Truth)
        rust_methods = {
            n: m for n, m in inspect.getmembers(rust_cls) 
            if inspect.isroutine(m) or inspect.ismethoddescriptor(m)
        }

        # 2. Check each relevant Rust method against Python Wrapper
        checked_count = 0
        for name, rust_method in rust_methods.items():
            if name.startswith("__") and name not in ["__init__", "__enter__", "__exit__"]:
                continue
            
            # Skip internal/private Rust methods if any (usually start with _)
            if name.startswith("_") and not name.startswith("__"):
                continue

            print(f"   Checking method: {name}...", end="")
            
            if not hasattr(py_cls, name):
                # It's okay if wrapper hides some low-level stuff, but warn.
                # Actually, for TheusEngine, we expect nearly 1:1 mapping for public API.
                print(" ⚠️ Missing in Python Wrapper (Intentional?)")
                continue

            py_method = getattr(py_cls, name)
            
            # Get Signatures
            try:
                rust_sig = inspect.signature(rust_method)
                py_sig = inspect.signature(py_method)
            except ValueError:
                print(" ⚠️ Cannot inspect signature (Built-in?)")
                continue

            # Compare Parameters
            rust_params = list(rust_sig.parameters.keys())
            py_params = list(py_sig.parameters.keys())

            # Filter 'self'
            if 'self' in rust_params: rust_params.remove('self')
            if 'self' in py_params: py_params.remove('self')
            
            # Filter 'args'/'kwargs' (wildcards)
            rust_params = [p for p in rust_params if p not in ['args', 'kwargs']]
            py_params = [p for p in py_params if p not in ['args', 'kwargs']]

            # Core Logic: Python Wrapper MUST support all args defined in Rust
            missing_params = [p for p in rust_params if p not in py_params]
            
            if missing_params:
                print(" ❌ FAILED!")
                print(f"      Rust:   {rust_params}")
                print(f"      Python: {py_params}")
                print(f"      Missing in Python: {missing_params}")
                self.fail(f"Method '{name}' in Python Wrapper is missing parameters: {missing_params}")
            
            print(" ✅ OK")
            checked_count += 1
            
        print(f"Verified {checked_count} methods.")

if __name__ == '__main__':
    unittest.main()
