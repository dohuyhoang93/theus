import unittest
import inspect

import theus.engine
import theus_core

class TestAPIParity(unittest.TestCase):
    """
    Defense Layer: Ensures Python Wrappers match Rust Core signatures correctly.
    Prevents INC-015 (Missing Parameter) from happening again.
    """

    # Explicit Allowlist for Rust methods that intentionally diverge from 1:1 wrapper method names:
    # - "property": mapped to a Python @property / setter on TheusEngine
    # - "internal": engine core implementation detail / internal callback (not public API on wrapper)
    PARITY_ALLOWLIST = {
        "set_strict_cas": {
            "type": "property",
            "target": "strict_cas",
            "reason": "Exposed via property setter `engine.strict_cas = bool`",
        },
        "set_strict_guards": {
            "type": "property",
            "target": "strict_guards",
            "reason": "Exposed via property setter `engine.strict_guards = bool`",
        },
        "report_success": {
            "type": "internal",
            "reason": "Internal telemetry callback called directly on self._core within execute()",
        },
        "report_conflict": {
            "type": "internal",
            "reason": "Internal telemetry callback called directly on self._core within execute()",
        },
        "set_audit_system": {
            "type": "internal",
            "reason": "Init-time wiring called directly on self._core within __init__()",
        },
        "execute_process_async": {
            "type": "internal",
            "reason": "Internal dispatch primitive called by execute(); public API is engine.execute()",
        },
    }

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
        sig_verified_count = 0
        property_count = 0
        internal_count = 0

        for name, rust_method in rust_methods.items():
            if name.startswith("__") and name not in ["__init__", "__enter__", "__exit__"]:
                continue
            
            # Skip internal/private Rust methods if any (usually start with _)
            if name.startswith("_") and not name.startswith("__"):
                continue

            print(f"   Checking method: {name}...", end="")
            
            if not hasattr(py_cls, name):
                if name in self.PARITY_ALLOWLIST:
                    rule = self.PARITY_ALLOWLIST[name]
                    if rule["type"] == "property":
                        prop_name = rule["target"]
                        self.assertTrue(
                            hasattr(py_cls, prop_name),
                            f"Parity mapping error: property '{prop_name}' missing on {py_cls.__name__}"
                        )
                        prop_obj = getattr(py_cls, prop_name)
                        self.assertIsInstance(
                            prop_obj,
                            property,
                            f"Parity mapping error: '{prop_name}' on {py_cls.__name__} is not a property"
                        )
                        self.assertIsNotNone(
                            prop_obj.fset,
                            f"Parity mapping error: property '{prop_name}' on {py_cls.__name__} has no setter (read-only)"
                        )
                        print(f" ✅ OK (Mapped to @property '{prop_name}' with setter)")
                        property_count += 1
                        continue
                    elif rule["type"] == "internal":
                        print(f" ✅ OK (Intentional Rust internal: {rule['reason']})")
                        internal_count += 1
                        continue

                # Unmapped and missing in Python wrapper -> HARD FAILURE
                print(" ❌ FAILED (Missing in wrapper and not in allowlist)")
                self.fail(
                    f"Rust Core method '{name}' has no counterpart in Python Wrapper {py_cls.__name__} "
                    f"and is not registered in PARITY_ALLOWLIST."
                )

            py_method = getattr(py_cls, name)
            
            # Get Signatures
            try:
                rust_sig = inspect.signature(rust_method)
                py_sig = inspect.signature(py_method)
            except (ValueError, TypeError):
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
                print(" ❌ FAILED (Missing parameters)!")
                print(f"      Rust:   {rust_params}")
                print(f"      Python: {py_params}")
                print(f"      Missing in Python: {missing_params}")
                self.fail(f"Method '{name}' in Python Wrapper is missing parameters: {missing_params}")

            # Order Check: parameters shared with Rust must appear in the exact same sequence
            py_matching_order = [p for p in py_params if p in rust_params]
            if py_matching_order != rust_params:
                print(" ❌ FAILED (Parameter order mismatch)!")
                print(f"      Rust:   {rust_params}")
                print(f"      Python: {py_params}")
                self.fail(
                    f"Method '{name}' parameter order mismatch: Rust expects {rust_params}, "
                    f"but Python has {py_matching_order}"
                )
            
            print(" ✅ OK")
            sig_verified_count += 1

        # Check for stale allowlist entries
        unused = set(self.PARITY_ALLOWLIST) - set(rust_methods)
        self.assertFalse(unused, f"Stale allowlist entries: {unused}")

        total_classified = sig_verified_count + property_count + internal_count
        print(f"Classified {total_classified} methods ({sig_verified_count} signature-verified, {property_count} properties, {internal_count} internal).")

if __name__ == '__main__':
    unittest.main()
